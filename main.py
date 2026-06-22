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


async def post_init(application):
    await start_scheduler(application.bot)


def main():
    app = Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).build()

    # Слушаем все сообщения в группе
    app.add_handler(MessageHandler(
        filters.TEXT & filters.ChatType.GROUPS & ~filters.COMMAND,
        handle_group_message
    ))

    # Ответы в личке (фидбэк от сотрудников)
    app.add_handler(MessageHandler(
        filters.TEXT & filters.ChatType.PRIVATE & ~filters.COMMAND,
        handle_feedback_response
    ))

    # Инлайн-кнопки (назначение исполнителя и т.д.)
    app.add_handler(CallbackQueryHandler(handle_callback))

    logger.info("Бот запущен")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
