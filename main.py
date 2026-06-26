import logging
import sys
import traceback

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

try:
    from telegram.ext import Application, MessageHandler, CommandHandler, filters, CallbackQueryHandler
    from handlers.message_handler import handle_group_message, handle_callback
    from handlers.feedback_handler import handle_feedback_response
    from handlers.admin_handler import cmd_adduser, cmd_removeuser, cmd_listusers
    from services.scheduler import start_scheduler
    from config import TELEGRAM_TOKEN

    async def debug_all(update, context):
        if update.message:
            logger.info(f"ПОЛУЧЕНО: chat_type={update.message.chat.type} text={update.message.text}")

    async def post_init(application):
        await start_scheduler(application.bot)

    def main():
        app = Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).build()
        app.add_handler(MessageHandler(filters.ALL, debug_all), group=0)
        app.add_handler(MessageHandler(
            filters.TEXT & filters.ChatType.GROUPS & ~filters.COMMAND,
            handle_group_message
        ), group=1)
        app.add_handler(MessageHandler(
            filters.TEXT & filters.ChatType.PRIVATE & ~filters.COMMAND,
            handle_feedback_response
        ), group=1)
        app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(CommandHandler("adduser", cmd_adduser))
    app.add_handler(CommandHandler("removeuser", cmd_removeuser))
    app.add_handler(CommandHandler("listusers", cmd_listusers))
    logger.info("Бот запущен")
        app.run_polling(drop_pending_updates=False)

    if __name__ == "__main__":
        main()

except Exception as e:
    logger.error(f"КРИТИЧЕСКАЯ ОШИБКА: {e}")
    traceback.print_exc()
    sys.exit(1)
