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

        reply_markup = InlineKeyboardMarkup(keyboard)

        bot_msg = await message.reply_text(
            f"📋 Обнаружена задача: *{task_data['name']}*\n\nКого назначить исполнителем?",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

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
