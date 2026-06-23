import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from services.claude_service import detect_task
from services.clickup_service import create_task, update_task_assignee
from services.storage import save_pending_assignment, get_pending_assignment, remove_pending_assignment, save_active_task
from utils.feedback_scheduler import schedule_feedback
from config import TEAM_MAP, CLICKUP_TO_TELEGRAM
import json

logger = logging.getLogger(__name__)

# Все члены команды для кнопок выбора исполнителя
TEAM_MEMBERS = [
    ("Анна Смирнова", "anna_smirnova"),
    ("Ольга Юрьева", "olga_yureva"),
    ("Екатерина", "kataz0601"),
    ("Мария Зеленова", "maria_zelenova"),
    ("Никита Акимушкин", "nikita_akimushkin"),
    ("Полина Заботина", "polina_zabotina"),
    ("Тамара Панченко", "tamara_panchenko"),
    ("Астемир Русланович", "astemir"),
]


async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or not message.text:
        return

    # Извлекаем упомянутых пользователей
    mentioned_users = []
    if message.entities:
        for entity in message.entities:
            if entity.type == "mention":
                username = message.text[entity.offset + 1:entity.offset + entity.length]
                mentioned_users.append(username)

    sender_name = message.from_user.full_name

    # Анализируем через Claude
    task_data = await detect_task(message.text, sender_name, mentioned_users)

    if not task_data:
        return  # Не задача, игнорируем

    logger.info(f"Обнаружена задача: {task_data.get('name')}")

    assignee_username = task_data.get("assignee_username")

    # Если упомянуто несколько пользователей — спрашиваем как назначить
    if len(mentioned_users) > 1:
        usernames_str = ", ".join([f"@{u}" for u in mentioned_users])
        keyboard = [
            [InlineKeyboardButton(f"👥 Назначить всем одну задачу", callback_data=f"multi_all:{message.message_id}")],
            [InlineKeyboardButton(f"📋 Каждому по отдельной задаче", callback_data=f"multi_each:{message.message_id}")],
            [InlineKeyboardButton(f"👤 Только одному (выбрать)", callback_data=f"multi_one:{message.message_id}")],
            [InlineKeyboardButton("❌ Это не задача", callback_data=f"multi_cancel:{message.message_id}")],
        ]
        bot_msg = await message.reply_text(
            f"📋 Обнаружена задача: *{task_data['name']}*\n"
            f"Упомянуты: {usernames_str}\n\nКак назначить?",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        # Сохраняем pending по message.message_id (тот же что в callback_data)
        save_pending_assignment(message.message_id, {
            "task_name": task_data["name"],
            "task_description": task_data.get("description", ""),
            "priority": task_data.get("priority", "normal"),
            "is_structured": task_data.get("has_subtasks", False),
            "subtasks": task_data.get("subtasks", []),
            "mentioned_users": mentioned_users,
            "group_chat_id": message.chat_id,
            "task_data": task_data,
        })
        return

    # Создаём задачу в ClickUp
    clickup_task = await create_task(
        name=task_data["name"],
        description=task_data.get("description", ""),
        priority=task_data.get("priority", "normal"),
        assignee_username=assignee_username,
        subtasks=task_data.get("subtasks") if task_data.get("has_subtasks") else None
    )

    if not clickup_task:
        await message.reply_text("⚠️ Не удалось создать задачу в ClickUp.")
        return

    task_id = clickup_task["id"]
    task_url = clickup_task.get("url", "")

    if assignee_username:
        # Исполнитель известен
        await message.reply_text(
            f"✅ Задача создана в ClickUp\n"
            f"📋 *{task_data['name']}*\n"
            f"👤 Исполнитель: @{assignee_username}\n"
            f"🔗 {task_url}",
            parse_mode="Markdown"
        )

        # Сохраняем и планируем фидбэк
        due_date = clickup_task.get("due_date")
        save_active_task(task_id, {
            "name": task_data["name"],
            "description": task_data.get("description", ""),
            "assignee_username": assignee_username,
            "is_structured": task_data.get("has_subtasks", False),
            "subtasks": task_data.get("subtasks", []),
            "due_date": due_date,
            "clickup_url": task_url,
            "group_chat_id": message.chat_id,
        })
        await schedule_feedback(task_id, assignee_username, due_date, context)

    else:
        # Исполнитель не определён — просим выбрать
        keyboard = []
        row = []
        for i, (name, username) in enumerate(TEAM_MEMBERS):
            row.append(InlineKeyboardButton(name, callback_data=f"assign:{task_id}:{username}:{message.message_id}"))
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)

        reply_markup = InlineKeyboardMarkup(keyboard)  # временно, обновим после

        keyboard.append([InlineKeyboardButton("❌ Это не задача", callback_data=f"not_task:{task_id}:0")])
        reply_markup = InlineKeyboardMarkup(keyboard)

        bot_msg = await message.reply_text(
            f"📋 Обнаружена задача: *{task_data['name']}*\n\nКого назначить исполнителем?",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        # Обновляем кнопку с реальным message_id
        keyboard[-1] = [InlineKeyboardButton("❌ Это не задача", callback_data=f"not_task:{task_id}:{bot_msg.message_id}")]
        await bot_msg.edit_reply_markup(InlineKeyboardMarkup(keyboard))

        # Сохраняем данные задачи для callback
        save_pending_assignment(bot_msg.message_id, {
            "task_id": task_id,
            "task_name": task_data["name"],
            "task_description": task_data.get("description", ""),
            "is_structured": task_data.get("has_subtasks", False),
            "subtasks": task_data.get("subtasks", []),
            "due_date": clickup_task.get("due_date"),
            "clickup_url": task_url,
            "group_chat_id": message.chat_id,
        })


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    if data.startswith("multi_cancel:"):
        original_msg_id = int(data.split(":")[1])
        remove_pending_assignment(original_msg_id)
        await query.edit_message_text("❌ Понял, не задача. Сообщение проигнорировано.")
        return

    if data.startswith("multi_all:"):
        original_msg_id = int(data.split(":")[1])
        pending = get_pending_assignment(original_msg_id)
        if not pending:
            await query.edit_message_text("⚠️ Сессия устарела.")
            return
        mentioned = pending["mentioned_users"]
        clickup_ids = [TEAM_MAP[u] for u in mentioned if u in TEAM_MAP]
        # Создаём одну задачу со всеми исполнителями
        import httpx as _httpx
        from config import CLICKUP_API_TOKEN as _TOKEN, CLICKUP_LIST_ID as _LIST_ID
        priority_map = {"urgent": 1, "high": 2, "normal": 3, "low": 4}
        payload = {
            "name": pending["task_name"],
            "description": pending["task_description"],
            "priority": priority_map.get(pending.get("priority", "normal"), 3),
            "assignees": clickup_ids,
        }
        async with _httpx.AsyncClient() as client:
            resp = await client.post(f"https://api.clickup.com/api/v2/list/{_LIST_ID}/task",
                headers={"Authorization": _TOKEN, "Content-Type": "application/json"}, json=payload)
            task = resp.json()
        task_id = task["id"]
        task_url = task.get("url", "")
        usernames_str = ", ".join([f"@{u}" for u in mentioned])
        await query.edit_message_text(
            f"✅ Задача создана в ClickUp\n📋 *{pending['task_name']}*\n👥 Исполнители: {usernames_str}\n🔗 {task_url}",
            parse_mode="Markdown"
        )
        for u in mentioned:
            save_active_task(f"{task_id}_{u}", {**pending, "assignee_username": u, "clickup_url": task_url, "task_id": task_id})
        remove_pending_assignment(original_msg_id)
        return

    if data.startswith("multi_each:"):
        original_msg_id = int(data.split(":")[1])
        pending = get_pending_assignment(original_msg_id)
        if not pending:
            await query.edit_message_text("⚠️ Сессия устарела.")
            return
        mentioned = pending["mentioned_users"]
        import httpx as _httpx
        from config import CLICKUP_API_TOKEN as _TOKEN, CLICKUP_LIST_ID as _LIST_ID
        priority_map = {"urgent": 1, "high": 2, "normal": 3, "low": 4}
        created = []
        async with _httpx.AsyncClient() as client:
            for u in mentioned:
                clickup_id = TEAM_MAP.get(u)
                payload = {
                    "name": pending["task_name"],
                    "description": pending["task_description"],
                    "priority": priority_map.get(pending.get("priority", "normal"), 3),
                    "assignees": [clickup_id] if clickup_id else [],
                }
                resp = await client.post(f"https://api.clickup.com/api/v2/list/{_LIST_ID}/task",
                    headers={"Authorization": _TOKEN, "Content-Type": "application/json"}, json=payload)
                task = resp.json()
                created.append((u, task["id"], task.get("url", "")))
                save_active_task(task["id"], {**pending, "assignee_username": u, "clickup_url": task.get("url", "")})
        tasks_text = "\n".join([f"👤 @{u} → {url}" for u, tid, url in created])
        await query.edit_message_text(
            f"✅ Созданы отдельные задачи:\n📋 *{pending['task_name']}*\n{tasks_text}",
            parse_mode="Markdown"
        )
        remove_pending_assignment(original_msg_id)
        return

    if data.startswith("multi_one:"):
        original_msg_id = int(data.split(":")[1])
        pending = get_pending_assignment(original_msg_id)
        if not pending:
            await query.edit_message_text("⚠️ Сессия устарела.")
            return
        # Показываем выбор из упомянутых
        mentioned = pending["mentioned_users"]
        keyboard = [[InlineKeyboardButton(f"@{u}", callback_data=f"multi_pick:{original_msg_id}:{u}")] for u in mentioned]
        keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data=f"multi_cancel:{original_msg_id}")])
        await query.edit_message_text(
            f"👤 Кому назначить задачу *{pending['task_name']}*?",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return

    if data.startswith("multi_pick:"):
        _, original_msg_id, username = data.split(":", 2)
        original_msg_id = int(original_msg_id)
        pending = get_pending_assignment(original_msg_id)
        if not pending:
            await query.edit_message_text("⚠️ Сессия устарела.")
            return
        import httpx as _httpx
        from config import CLICKUP_API_TOKEN as _TOKEN, CLICKUP_LIST_ID as _LIST_ID
        priority_map = {"urgent": 1, "high": 2, "normal": 3, "low": 4}
        clickup_id = TEAM_MAP.get(username)
        payload = {
            "name": pending["task_name"],
            "description": pending["task_description"],
            "priority": priority_map.get(pending.get("priority", "normal"), 3),
            "assignees": [clickup_id] if clickup_id else [],
        }
        async with _httpx.AsyncClient() as client:
            resp = await client.post(f"https://api.clickup.com/api/v2/list/{_LIST_ID}/task",
                headers={"Authorization": _TOKEN, "Content-Type": "application/json"}, json=payload)
            task = resp.json()
        task_url = task.get("url", "")
        await query.edit_message_text(
            f"✅ Задача создана в ClickUp\n📋 *{pending['task_name']}*\n👤 Исполнитель: @{username}\n🔗 {task_url}",
            parse_mode="Markdown"
        )
        save_active_task(task["id"], {**pending, "assignee_username": username, "clickup_url": task_url})
        remove_pending_assignment(original_msg_id)
        return

    if data.startswith("not_task:"):
        parts = data.split(":")
        task_id = parts[1]
        original_msg_id = parts[2]
        import httpx as _httpx
        from config import CLICKUP_API_TOKEN as _TOKEN
        async with _httpx.AsyncClient() as client:
            await client.delete(
                f"https://api.clickup.com/api/v2/task/{task_id}",
                headers={"Authorization": _TOKEN, "Content-Type": "application/json"}
            )
        remove_pending_assignment(int(original_msg_id))
        await query.edit_message_text("❌ Понял, не задача. Сообщение проигнорировано.")
        return

    if data.startswith("assign:"):
        _, task_id, username, original_msg_id = data.split(":")
        pending = get_pending_assignment(int(original_msg_id))

        if not pending:
            await query.edit_message_text("⚠️ Сессия устарела, задача уже назначена.")
            return

        # Назначаем в ClickUp
        clickup_user_id = TEAM_MAP.get(username)
        if clickup_user_id:
            await update_task_assignee(task_id, clickup_user_id)

        # Сохраняем активную задачу
        save_active_task(task_id, {
            **pending,
            "assignee_username": username,
        })

        remove_pending_assignment(int(original_msg_id))

        # Находим отображаемое имя
        display_name = next((name for name, u in TEAM_MEMBERS if u == username), username)

        await query.edit_message_text(
            f"✅ Задача создана в ClickUp\n"
            f"📋 *{pending['task_name']}*\n"
            f"👤 Исполнитель: {display_name}\n"
            f"🔗 {pending.get('clickup_url', '')}",
            parse_mode="Markdown"
        )

        # Планируем фидбэк
        await schedule_feedback(task_id, username, pending.get("due_date"), context)
