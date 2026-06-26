import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from services.config_manager import add_user, remove_user, list_users

logger = logging.getLogger(__name__)

ADMIN_ID = 120515403
WAITING_ADD_USERNAME, WAITING_ADD_CLICKUP_ID, WAITING_REMOVE_USERNAME = range(3)


def admin_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_ID:
            return
        return await func(update, context)
    return wrapper


@admin_only
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("\U0001f465 \u0421\u043f\u0438\u0441\u043e\u043a \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u0435\u0439", callback_data="admin:list")],
        [InlineKeyboardButton("\u2795 \u0414\u043e\u0431\u0430\u0432\u0438\u0442\u044c \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044f", callback_data="admin:add")],
        [InlineKeyboardButton("\u2796 \u0423\u0434\u0430\u043b\u0438\u0442\u044c \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044f", callback_data="admin:remove")],
    ]
    await update.message.reply_text(
        "\U0001f916 \u0410\u0434\u043c\u0438\u043d-\u043f\u0430\u043d\u0435\u043b\u044c DCT Bot",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


@admin_only
async def cmd_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cmd_start(update, context)


async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != ADMIN_ID:
        return
    await query.answer()
    data = query.data

    if data == "admin:list":
        users = list_users()
        if not users:
            text = "\u0421\u043f\u0438\u0441\u043e\u043a \u043f\u0443\u0441\u0442."
        else:
            text = "\U0001f465 \u041f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u0438:\n"
            for username, clickup_id in users.items():
                text += f"  @{username} \u2192 {clickup_id}\n"
        keyboard = [[InlineKeyboardButton("\u2190 \u041d\u0430\u0437\u0430\u0434", callback_data="admin:back")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "admin:add":
        await query.edit_message_text(
            "\u2795 \u0412\u0432\u0435\u0434\u0438 @username \u043d\u043e\u0432\u043e\u0433\u043e \u0441\u043e\u0442\u0440\u0443\u0434\u043d\u0438\u043a\u0430:\n(\u043d\u0430\u043f\u0440\u0438\u043c\u0435\u0440: @ivan)"
        )
        context.user_data["admin_action"] = "add_username"

    elif data == "admin:remove":
        await query.edit_message_text(
            "\u2796 \u0412\u0432\u0435\u0434\u0438 @username \u0434\u043b\u044f \u0443\u0434\u0430\u043b\u0435\u043d\u0438\u044f:"
        )
        context.user_data["admin_action"] = "remove_username"

    elif data == "admin:back":
        keyboard = [
            [InlineKeyboardButton("\U0001f465 \u0421\u043f\u0438\u0441\u043e\u043a \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u0435\u0439", callback_data="admin:list")],
            [InlineKeyboardButton("\u2795 \u0414\u043e\u0431\u0430\u0432\u0438\u0442\u044c \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044f", callback_data="admin:add")],
            [InlineKeyboardButton("\u2796 \u0423\u0434\u0430\u043b\u0438\u0442\u044c \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044f", callback_data="admin:remove")],
        ]
        await query.edit_message_text(
            "\U0001f916 \u0410\u0434\u043c\u0438\u043d-\u043f\u0430\u043d\u0435\u043b\u044c DCT Bot",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def admin_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not update.message or not update.message.text:
        return

    action = context.user_data.get("admin_action")
    text = update.message.text.strip()

    if action == "add_username":
        username = text.lstrip("@").lower()
        context.user_data["new_username"] = username
        context.user_data["admin_action"] = "add_clickup_id"
        await update.message.reply_text(
            f"\u0422\u0435\u043f\u0435\u0440\u044c \u0432\u0432\u0435\u0434\u0438 ClickUp ID \u0434\u043b\u044f @{username}:"
        )

    elif action == "add_clickup_id":
        try:
            clickup_id = int(text)
            username = context.user_data.get("new_username")
            add_user(username, clickup_id)
            context.user_data.clear()
            keyboard = [[InlineKeyboardButton("\u2190 \u041c\u0435\u043d\u044e", callback_data="admin:back")]]
            await update.message.reply_text(
                f"\u2705 @{username} (ClickUp ID: {clickup_id}) \u0434\u043e\u0431\u0430\u0432\u043b\u0435\u043d!",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except ValueError:
            await update.message.reply_text("\u0412\u0432\u0435\u0434\u0438 \u0447\u0438\u0441\u043b\u043e\u0432\u043e\u0439 ID:")

    elif action == "remove_username":
        username = text.lstrip("@").lower()
        success = remove_user(username)
        context.user_data.clear()
        keyboard = [[InlineKeyboardButton("\u2190 \u041c\u0435\u043d\u044e", callback_data="admin:back")]]
        if success:
            await update.message.reply_text(
                f"\u2705 @{username} \u0443\u0434\u0430\u043b\u0451\u043d.",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await update.message.reply_text(
                f"\u274c @{username} \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d.",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )


@admin_only
async def cmd_adduser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) != 2:
        await update.message.reply_text("\u0418\u0441\u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u043d\u0438\u0435: /adduser @username clickup_id")
        return
    username = args[0].lstrip("@").lower()
    try:
        clickup_id = int(args[1])
    except ValueError:
        await update.message.reply_text("clickup_id \u0434\u043e\u043b\u0436\u0435\u043d \u0431\u044b\u0442\u044c \u0447\u0438\u0441\u043b\u043e\u043c.")
        return
    add_user(username, clickup_id)
    await update.message.reply_text(f"\u2705 @{username} ({clickup_id}) \u0434\u043e\u0431\u0430\u0432\u043b\u0435\u043d.")


@admin_only
async def cmd_removeuser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) != 1:
        await update.message.reply_text("\u0418\u0441\u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u043d\u0438\u0435: /removeuser @username")
        return
    username = args[0].lstrip("@").lower()
    success = remove_user(username)
    if success:
        await update.message.reply_text(f"\u2705 @{username} \u0443\u0434\u0430\u043b\u0451\u043d.")
    else:
        await update.message.reply_text(f"\u274c @{username} \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d.")


@admin_only
async def cmd_listusers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = list_users()
    if not users:
        await update.message.reply_text("\u0421\u043f\u0438\u0441\u043e\u043a \u043f\u0443\u0441\u0442.")
        return
    text = "\U0001f465 \u041f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u0438:\n"
    for username, clickup_id in users.items():
        text += f"  @{username} \u2192 {clickup_id}\n"
    await update.message.reply_text(text)
