import logging
from telegram import Update
from telegram.ext import ContextTypes
from services.claude_service import analyze_feedback
from services.storage import get_feedback_session, clear_feedback_session, add_feedback_to_task
from services.clickup_service import add_task_comment

logger = logging.getLogger(__name__)

# Менеджер которому идут алерты о плохом фидбэке
MANAGER_USERNAME = "ivanmaryukha"


async def handle_feedback_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    text = update.message.text

    session = get_feedback_session(user.id)
    if not session:
        await update.message.reply_text(
            "Привет! Я бот Yumbaker. Я пишу когда нужно отчитаться по задаче 📋"
        )
        return

    task_id = session["task_id"]
    task_name = session["task_name"]
    task_description = session.get("task_description", "")
    is_structured = session.get("is_structured", False)

    await update.message.reply_text("Анализирую твой ответ... ⏳")

    # Анализируем фидбэк через Claude
    analysis = await analyze_feedback(task_name, task_description, text, is_structured)

    # Сохраняем в storage и ClickUp
    feedback_record = {
        "user_id": user.id,
        "username": user.username,
        "text": text,
        "analysis": analysis,
    }
    add_feedback_to_task(task_id, feedback_record)
    await add_task_comment(
        task_id,
        f"📝 Фидбэк от @{user.username}:\n{text}\n\n"
        f"🤖 Анализ: {analysis.get('summary', '')}\n"
        f"Оценка: {analysis.get('score', 0)}/5"
    )

    clear_feedback_session(user.id)

    if analysis.get("is_adequate"):
        response = f"Спасибо за обновление! ✅\n\n_{analysis.get('summary', '')}_"
        if analysis.get("has_blockers"):
            response += f"\n\n⚠️ Вижу блокер: {analysis.get('blockers', '')}. Передам менеджеру."
        await update.message.reply_text(response, parse_mode="Markdown")
    else:
        await update.message.reply_text(
            f"Хм, мне нужно больше конкретики 🙏\n\n"
            f"{'Пожалуйста, ответь по каждому пункту задачи.' if is_structured else 'Расскажи конкретно: что уже сделано и что осталось?'}"
        )

    # Алертим менеджера если плохой фидбэк или есть блокеры
    if not analysis.get("is_adequate") or analysis.get("has_blockers"):
        try:
            await context.bot.send_message(
                chat_id=f"@{MANAGER_USERNAME}",
                text=f"⚠️ Внимание по задаче *{task_name}*\n"
                     f"Исполнитель: @{user.username}\n"
                     f"Статус: {analysis.get('summary', text[:100])}\n"
                     f"{'🚧 Блокер: ' + analysis.get('blockers', '') if analysis.get('has_blockers') else '❓ Фидбэк неадекватный'}\n\n"
                     f"Рекомендация: {analysis.get('recommendation', '')}",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.warning(f"Не удалось уведомить менеджера: {e}")
