import anthropic
import json
from config import ANTHROPIC_API_KEY

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


async def detect_task(message_text: str, sender_name: str, mentioned_users: list[str]) -> dict | None:
    """
    Анализирует сообщение и определяет, является ли оно задачей.
    Возвращает структуру задачи или None если это не задача.
    """
    prompt = f"""Ты анализируешь сообщение из рабочего Telegram-чата ресторанного бизнеса.

Сообщение от: {sender_name}
Упомянутые пользователи: {', '.join(mentioned_users) if mentioned_users else 'никто'}
Текст: "{message_text}"

Определи: является ли это сообщение ЗАДАЧЕЙ (поручением, которое нужно выполнить)?

Задача — это сообщение с конкретным действием и объектом: "починить", "сделать", "подготовить", "договориться", "установить", "закупить" и т.п.
НЕ задача — вопросы, обсуждения, приветствия, мнения, информационные сообщения.

Если это задача, верни JSON:
{{
  "is_task": true,
  "name": "краткое название задачи (до 80 символов)",
  "description": "полное описание задачи с деталями из сообщения",
  "priority": "urgent|high|normal|low",
  "assignee_username": "telegram username исполнителя если явно упомянут, иначе null",
  "has_subtasks": true/false,
  "subtasks": ["подзадача 1", "подзадача 2"] // если есть этапы выполнения
}}

Если это НЕ задача, верни:
{{"is_task": false}}

Верни ТОЛЬКО JSON, без пояснений."""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )

    try:
        result = json.loads(response.content[0].text)
        return result if result.get("is_task") else None
    except Exception:
        return None


async def analyze_feedback(task_name: str, task_description: str, feedback_text: str, is_structured: bool) -> dict:
    """
    Анализирует фидбэк от сотрудника на адекватность и информативность.
    """
    if is_structured:
        context = f"""Задача структурированная с подпунктами.
Описание задачи: {task_description}
Ожидается ответ по каждому пункту."""
    else:
        context = f"""Задача: {task_name}
Ожидается: актуальный статус выполнения."""

    prompt = f"""Ты анализируешь фидбэк сотрудника по рабочей задаче.

{context}

Фидбэк сотрудника: "{feedback_text}"

Оцени фидбэк по критериям:
1. Информативность: есть ли конкретная информация о прогрессе?
2. Адекватность: соответствует ли ответ формату задачи?
3. Наличие блокеров: упомянуты ли проблемы или препятствия?

Верни JSON:
{{
  "score": 1-5,  // общая оценка качества фидбэка
  "is_adequate": true/false,
  "summary": "краткое резюме статуса в 1-2 предложения",
  "has_blockers": true/false,
  "blockers": "описание блокеров если есть",
  "recommendation": "рекомендация менеджеру если фидбэк неадекватный"
}}

Верни ТОЛЬКО JSON."""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}]
    )

    try:
        return json.loads(response.content[0].text)
    except Exception:
        return {"score": 0, "is_adequate": False, "summary": feedback_text, "has_blockers": False}


async def generate_weekly_report(tasks_data: list[dict], employee_name: str) -> dict:
    """
    Генерирует еженедельный отчёт по сотруднику.
    """
    tasks_json = json.dumps(tasks_data, ensure_ascii=False, indent=2)

    prompt = f"""Ты составляешь еженедельный отчёт об эффективности сотрудника.

Сотрудник: {employee_name}
Данные по задачам за неделю:
{tasks_json}

Составь два варианта отчёта:

1. ПОДРОБНЫЙ (для сотрудника) — включи:
- Выполненные задачи с оценкой
- Незавершённые задачи и причины
- Качество фидбэка
- Конкретные рекомендации на следующую неделю

2. КРАТКИЙ (для общего чата) — 3-5 строк:
- Имя сотрудника
- Ключевые результаты
- Общая оценка (эмодзи + слово)

Верни JSON:
{{
  "detailed": "подробный отчёт в markdown",
  "summary": "краткий отчёт для общего чата",
  "overall_score": 1-10,
  "completed_tasks": число,
  "pending_tasks": число
}}

Верни ТОЛЬКО JSON."""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )

    try:
        return json.loads(response.content[0].text)
    except Exception:
        return {"detailed": "Ошибка генерации отчёта", "summary": "Ошибка", "overall_score": 0}
