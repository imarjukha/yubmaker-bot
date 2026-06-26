import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from services.claude_service import detect_task
from services.clickup_service import create_task, update_task_assignee
from services.storage import save_pending_assignment, get_pending_assignment, remove_pending_assignment, save_active_task
from utils.feedback_scheduler import schedule_feedback
from services.config_manager import get_team_map, get_clickup_to_telegram
from config import TEAM_MAP, CLICKUP_TO_TELEGRAM
import json

logger = logging.getLogger(__name__)

# Все члены команды для кнопок выбора исполнителя
TEAM_MEMBERS = [
    ("Анна Смирнова", "heyannett"),
    ("Ольга Юрьева", "volgatheocean"),
    ("Екатерина", "rinaa_k"),
    ("Мария Зеленова", "zelemash"),
    ("Никита Акимушкин", "westcost777"),
    ("Полина Заботина", "z_polli"),
    ("Тамара Панченко", "panchenko_tv"),
    ("Астемир Русланович", "asti_kh"),
]


async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or not message.text:
        return

    # Извлекаем упомянутых пользователей — из entities И из текста напрямую
    import re
    mentioned_users = []
    if message.entities:
        for entity in message.entities:
            if entity.type == "mention":
                username = message.text[entity.offset + 1:entity.offset + entity.length].lower()
                if username not in mentioned_users:
                    mentioned_users.append(username)
    # Дополнительно парсим текст — ловим тех у кого закрыты упоминания
    text_mentions = re.findall(r'@(\w+)', message.text)
    for u in text_mentions:
        if u.lower() not in mentioned_users:
            mentioned_users.append(u.lower())

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
            f"📋 {task_data['name']}\n"
            f"👤 Исполнитель: @{assignee_username}\n"
            f"🔗 {task_url}",
            
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
        keyboard = []
        for name, username in TEAM_MEMBERS:
            keyboard.append([InlineKeyboardButton(
                "◻️ " + name,
                callback_data="toggle:" + task_id + ":0:" + username
            )])
        keyboard.append([InlineKeyboardButton("✅ Назначить выбранных", callback_data="assign_selected:" + task_id + ":0")])
        keyboard.append([InlineKeyboardButton("❌ Это не задача", callback_data="not_task:" + task_id + ":0")])

        bot_msg = await message.reply_text(
            "Обнаружена задача: " + task_data["name"] + "\n\nВыбери исполнителей:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

        keyboard2 = []
        for name, username in TEAM_MEMBERS:
            keyboard2.append([InlineKeyboardButton(
                "◻️ " + name,
                callback_data="toggle:" + task_id + ":" + str(bot_msg.message_id) + ":" + username
            )])
        keyboard2.append([InlineKeyboardButton("✅ Назначить выбранных", callback_data="assign_selected:" + task_id + ":" + str(bot_msg.message_id))])
        keyboard2.append([InlineKeyboardButton("❌ Это не задача", callback_data="not_task:" + task_id + ":" + str(bot_msg.message_id))])
        await bot_msg.edit_reply_markup(InlineKeyboardMarkup(keyboard2))

        save_pending_assignment(bot_msg.message_id, {
            "task_id": task_id,
            "task_name": task_data["name"],
            "task_description": task_data.get("description", ""),
            "is_structured": task_data.get("has_subtasks", False),
            "subtasks": task_data.get("subtasks", []),
            "due_date": clickup_task.get("due_date"),
            "clickup_url": task_url,
            "group_chat_id": message.chat_id,
            "selected_users": [],
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
        clickup_id = get_team_map().get(username)
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
            
        )
        save_active_task(task["id"], {**pending, "assignee_username": username, "clickup_url": task_url})
        remove_pending_assignment(original_msg_id)
        return

    if data.startswith("toggle:"):
        parts = data.split(":")
        task_id = parts[1]
        msg_id = int(parts[2])
        username = parts[3]
        pending = get_pending_assignment(msg_id)
        if not pending:
            await query.answer("\u0421\u0435\u0441\u0441\u0438\u044f \u0443\u0441\u0442\u0430\u0440\u0435\u043b\u0430")
            return
        selected = pending.get("selected_users", [])
        if username in selected:
            selected.remove(username)
        else:
            selected.append(username)
        pending["selected_users"] = selected
        save_pending_assignment(msg_id, pending)
        keyboard = []
        for name, uname in TEAM_MEMBERS:
            mark = "\u2705" if uname in selected else "\u25fb\ufe0f"
            keyboard.append([InlineKeyboardButton(
                mark + " " + name,
                callback_data="toggle:" + task_id + ":" + str(msg_id) + ":" + uname
            )])
        count = len(selected)
        btn_label = "\u2705 \u041d\u0430\u0437\u043d\u0430\u0447\u0438\u0442\u044c \u0432\u044b\u0431\u0440\u0430\u043d\u043d\u044b\u0445 (" + str(count) + ")" if count > 0 else "\u2705 \u041d\u0430\u0437\u043d\u0430\u0447\u0438\u0442\u044c \u0432\u044b\u0431\u0440\u0430\u043d\u043d\u044b\u0445"
        keyboard.append([InlineKeyboardButton(btn_label, callback_data="assign_selected:" + task_id + ":" + str(msg_id))])
        keyboard.append([InlineKeyboardButton("\u274c \u042d\u0442\u043e \u043d\u0435 \u0437\u0430\u0434\u0430\u0447\u0430", callback_data="not_task:" + task_id + ":" + str(msg_id))])
        await query.edit_message_reply_markup(InlineKeyboardMarkup(keyboard))
        await query.answer()
        return

    if data.startswith("assign_selected:"):
        parts = data.split(":")
        task_id = parts[1]
        msg_id = int(parts[2])
        pending = get_pending_assignment(msg_id)
        if not pending:
            await query.edit_message_text("\u0421\u0435\u0441\u0441\u0438\u044f \u0443\u0441\u0442\u0430\u0440\u0435\u043b\u0430.")
            return
        selected = pending.get("selected_users", [])
        if not selected:
            await query.answer("\u0412\u044b\u0431\u0435\u0440\u0438 \u0445\u043e\u0442\u044f \u0431\u044b \u043e\u0434\u043d\u043e\u0433\u043e!")
            return
        import httpx as _httpx
        from config import CLICKUP_API_TOKEN as _TOKEN
        team = get_team_map()
        clickup_ids = [team[u] for u in selected if u in team]
        async with _httpx.AsyncClient() as client:
            await client.put(
                "https://api.clickup.com/api/v2/task/" + task_id,
                headers={"Authorization": _TOKEN, "Content-Type": "application/json"},
                json={"assignees": {"add": clickup_ids, "rem": []}}
            )
        names = ", ".join([name for name, u in TEAM_MEMBERS if u in selected])
        task_url = pending.get("clickup_url", "")
        await query.edit_message_text(
            "\u2705 \u0417\u0430\u0434\u0430\u0447\u0430 \u0441\u043e\u0437\u0434\u0430\u043d\u0430 \u0432 ClickUp\n" + pending["task_name"] + "\n\u0418\u0441\u043f\u043e\u043b\u043d\u0438\u0442\u0435\u043b\u0438: " + names + "\n" + task_url
        )
        for u in selected:
            save_active_task(task_id + "_" + u, dict(pending, assignee_username=u))
        remove_pending_assignment(msg_id)
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
        clickup_user_id = get_team_map().get(username)
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
            
        )

        # Планируем фидбэк
        await schedule_feedback(task_id, username, pending.get("due_date"), context)
