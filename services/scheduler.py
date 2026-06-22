from typing import Optional
import logging
from datetime import datetime, timedelta
from telegram import Bot
from services.claude_service import generate_weekly_report
from services.clickup_service import get_tasks_for_user
from services.storage import get_active_tasks
from config import TEAM_MAP, CLICKUP_TO_TELEGRAM

logger = logging.getLogger(__name__)

# ID общего чата — замени на реальный после добавления бота в группу
GROUP_CHAT_ID = None  # Например: -1001234567890

# Список команды для отчёта: (отображаемое имя, telegram_username, clickup_user_id)
TEAM_FOR_REPORT = [
    ("Анна Смирнова", "heyannett", 99761883),
    ("Ольга Юрьева", "volgatheocean", 99763886),
    ("Екатерина", "rinaa_k", 99844168),
    ("Мария Зеленова", "Zelemash", 99761884),
    ("Никита Акимушкин", "westcost777", 99761882),
    ("Полина Заботина", "z_polli", 99761939),
    ("Тамара Панченко", "panchenko_tv", 99763894),
    ("Астемир Русланович", "Asti_Kh", 99761885),
]


async def start_scheduler(bot: Bot):
    """Запускает еженедельный планировщик отчётов (каждую пятницу в 18:00)."""
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        send_weekly_reports,
        "cron",
        day_of_week="fri",
        hour=18,
        minute=0,
        args=[bot]
    )
    scheduler.start()
    logger.info("Планировщик еженедельных отчётов запущен (пятница 18:00)")


async def send_weekly_reports(bot: Bot):
    """Генерирует и отправляет еженедельные отчёты."""
    logger.info("Генерация еженедельных отчётов...")
    week_ago = datetime.now() - timedelta(days=7)
    summary_lines = ["📊 *Еженедельный отчёт команды*\n"]

    for display_name, tg_username, clickup_id in TEAM_FOR_REPORT:
        try:
            # Получаем задачи из ClickUp
            tasks = await get_tasks_for_user(clickup_id, due_date_from=week_ago)

            # Получаем фидбэки из storage
            active = get_active_tasks()
            tasks_with_feedback = []
            for task in tasks:
                task_id = task["id"]
                feedback_data = active.get(task_id, {}).get("feedbacks", [])
                tasks_with_feedback.append({
                    "name": task["name"],
                    "status": task.get("status", {}).get("status", "unknown"),
                    "priority": task.get("priority", {}).get("priority", "normal"),
                    "feedbacks": feedback_data,
                    "due_date": task.get("due_date"),
                })

            if not tasks_with_feedback:
                summary_lines.append(f"• {display_name}: нет задач за неделю")
                continue

            # Генерируем отчёт через Claude
            report = await generate_weekly_report(tasks_with_feedback, display_name)

            # Отправляем подробный отчёт лично
            try:
                await bot.send_message(
                    chat_id=f"@{tg_username}",
                    text=f"📋 *Твой отчёт за неделю*\n\n{report['detailed']}",
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.warning(f"Не удалось отправить личный отчёт @{tg_username}: {e}")

            # Добавляем краткую строку для общего чата
            score = report.get("overall_score", 0)
            emoji = "🟢" if score >= 8 else "🟡" if score >= 5 else "🔴"
            summary_lines.append(
                f"{emoji} *{display_name}*: {report.get('summary', '')}"
            )

        except Exception as e:
            logger.error(f"Ошибка при генерации отчёта для {display_name}: {e}")
            summary_lines.append(f"• {display_name}: ошибка генерации отчёта")

    # Отправляем сводный отчёт в общий чат
    if GROUP_CHAT_ID:
        try:
            await bot.send_message(
                chat_id=GROUP_CHAT_ID,
                text="\n\n".join(summary_lines),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Не удалось отправить сводный отчёт в общий чат: {e}")
