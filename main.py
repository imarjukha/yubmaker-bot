import logging
import asyncio
from telegram.ext import Application, MessageHandler, CommandHandler, filters, CallbackQueryHandler
from handlers.message_handler import handle_group_message, handle_callback
from handlers.feedback_handler import handle_feedback_response
from services.scheduler import start_scheduler
from config import TELEGRAM_TOKEN

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def debug_all(update, context):
    logger.info(f"ПОЛУЧЕНО СООБЩЕНИЕ: chat_type={update.message.chat.type} text={update.message.text}")


async def post_init(application):
    await start_scheduler(application.bot)


def main():
    app = Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).build()

    # Дебаг — логируем все сообщения
    app.add_handler(MessageHandler(filters.ALL, debug_all), group=0)

    # Слушаем все сообщения в группе
    app.add_handler(MessageHandler(
        filters.TEXT & filters.ChatType.GROUPS & ~filters.COMMAND,
        handle_group_message
    ), group=1)

    # Ответы в личке
    app.add_handler(MessageHandler(
        filters.TEXT & filters.ChatType.PRIVATE & ~filters.COMMAND,
        handle_feedback_response
    ), group=1)

    app.add_handler(CallbackQueryHandler(handle_callback))

    logger.info("Бот запущен")
    app.run_polling(drop_pending_updates=False)


if __name__ == "__main__":
    main()
