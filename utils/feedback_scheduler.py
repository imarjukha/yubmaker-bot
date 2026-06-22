import logging
from datetime import datetime, timedelta
from telegram.ext import ContextTypes
from config import CLICKUP_TO_TELEGRAM

logger = logging.getLogger(__name__)


async def schedule_feedback(task_id, assignee_username, due_date_ms, context):
    if not due_date_ms:
        return

    now = datetime.now()
    due = datetime.fromtimestamp(int(due_date_ms) / 1000)
    duration_days = (due - now).days

    checkpoints = []

    if duration_days < 7:
        checkpoints = [due - timedelta(days=1)]
    elif duration_days <= 14:
        mid = now + timedelta(days=duration_days // 2)
        checkpoints = [mid, due - timedelta(days=1)]
    else:
        checkpoint = now + timedelta(days=5)
        while checkpoint < due - timedelta(days=2):
            checkpoints.append(checkpoint)
            checkpoint += timedelta(days=5)
        checkpoints.append(due - timedelta(days=1))

    for checkpoint in checkpoints:
        delay = (checkpoint - now).total_seconds()
        if delay > 0:
            context.job_queue.run_once(
                send_feedback_request,
                when=delay,
                data={
                    "task_id": task_id,
                    "assignee_username": assignee_username,
                    "is_final": checkpoint >= due - timedelta(days=1),
                },
                name=f"feedback_{task_id}_{checkpoint.date()}"
            )


async def send_feedback_request(context):
    from services.storage import get_active_tasks, save_feedback_session

    job = context.job
    data = job.data
    task_id = data["task_id"]
    assignee_username = data["assignee_username"]
    is_final = data.get("is_final", False)

    tasks = get_active_tasks()
    task = tasks.get(task_id)
    if not task:
        return

    task_name = task["name"]
    is_structured = task.get("is_structured", False)
    subtasks = task.get("subtasks", [])

    if is_structured and subtasks:
        subtasks_text = "\n".join([f"  {i+1}. {st}" for i, st in enumerate(subtasks)])
        message = (
            f"{'Финальный отчёт' if is_final else 'Промежуточный статус'} по задаче:\n\n"
            f"*{task_name}*\n\n"
            f"Ответь по каждому пункту:\n{subtasks_text}\n\n"
            f"Напиши статус каждого пункта 👇"
        )
    else:
        message = (
            f"{'Финальный отчёт' if is_final else 'Промежуточный статус'} по задаче:\n\n"
            f"*{task_name}*\n\n"
            f"Напиши актуальный статус: что уже сделано, что осталось? 👇"
        )

    try:
        sent = await context.bot.send_message(
            chat_id=f"@{assignee_username}",
            text=message,
            parse_mode="Markdown"
        )
        save_feedback_session(sent.chat_id, {
            "task_id": task_id,
            "task_name": task_name,
            "task_description": task.get("description", ""),
            "is_structured": is_structured,
            "subtasks": subtasks,
        })
    except Exception as e:
        logger.error(f"Не удалось отправить запрос фидбэка @{assignee_username}: {e}")
