import logging
from telegram import Update
from telegram.ext import ContextTypes
from services.config_manager import add_user, remove_user, list_users

logger = logging.getLogger(__name__)

ADMIN_ID = 120515403


def admin_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_ID:
            await update.message.reply_text("⛔ Нет доступа.")
            return
        return await func(update, context)
    return wrapper


@admin_only
async def cmd_adduser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /adduser @username clickup_id
    Пример: /adduser @ivan 99761883
    """
    args = context.args
    if len(args) != 2:
        await update.message.reply_text(
            "Использование: /adduser @username clickup_id\n"
            "Пример: /adduser @ivan 99761883"
        )
        return

    username = args[0].lstrip("@").lower()
    try:
        clickup_id = int(args[1])
    except ValueError:
        await update.message.reply_text("❌ clickup_id должен быть числом.")
        return

    add_user(username, clickup_id)
    await update.message.reply_text(f"✅ Пользователь @{username} (ClickUp ID: {clickup_id}) добавлен.")


@admin_only
async def cmd_removeuser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /removeuser @username
    """
    args = context.args
    if len(args) != 1:
        await update.message.reply_text("Использование: /removeuser @username")
        return

    username = args[0].lstrip("@").lower()
    success = remove_user(username)
    if success:
        await update.message.reply_text(f"✅ Пользователь @{username} удалён.")
    else:
        await update.message.reply_text(f"❌ Пользователь @{username} не найден.")


@admin_only
async def cmd_listusers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /listusers — показать всех пользователей
    """
    users = list_users()
    if not users:
        await update.message.reply_text("Список пользователей пуст.")
        return

    text = "👥 *Пользователи:*\n"
    for username, clickup_id in users.items():
        text += f"• @{username} → ClickUp ID: {clickup_id}\n"
    await update.message.reply_text(text, parse_mode="Markdown")
