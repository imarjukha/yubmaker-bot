import anthropic
import json
import os

def _get_client():
    from config import ANTHROPIC_API_KEY
    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

async def detect_task(message_text, sender_name, mentioned_users):
    client = _get_client()
    prompt = f"""Ты анализируешь сообщение из рабочего Telegram-чата ресторанного бизнеса.

Сообщение от: {sender_name}
Упомянутые пользователи: {', '.join(mentioned_users) if mentioned_users else 'никто'}
Текст: "{message_text}"

Определи: является ли это сообщение ЗАДАЧЕЙ?
Задача — сообщение с конкретным действием: "починить", "сделать", "подготовить", "договориться", "установить", "закупить" и т.п.
НЕ задача — только чистые вопросы без действий, приветствия, мнения без поручений.
ВАЖНО: если в сообщении есть хотя бы один глагол-поручение (в том числе в вежливой форме: "пожалуйста", "пришлите", "сделайте", "выгрузите" и т.п.) — это ЗАДАЧА. Наличие нескольких упомянутых пользователей не делает сообщение не-задачей — это просто задача с несколькими потенциальными исполнителями. (определить, прописать, сделать, подготовить, написать, купить, договориться, прислать, организовать и т.п.) — это ЗАДАЧА, даже если сообщение длинное или содержит контекст и пояснения. Длина сообщения не влияет на то, является ли оно задачей.

Если задача, верни JSON:
{{"is_task": true, "name": "название до 80 символов", "description": "описание", "priority": "urgent|high|normal|low", "assignee_username": "username или null", "has_subtasks": false, "subtasks": []}}

Если НЕ задача:
{{"is_task": false}}

Важно про даты: в сообщении может быть несколько дат (например дата мероприятия и дата дедлайна). Дедлайн задачи — это дата после слов "срок", "до", "к", "выполнить к". Дата самого мероприятия или события — это часть описания задачи, не дедлайн.

Только JSON, без пояснений."""

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

async def analyze_feedback(task_name, task_description, feedback_text, is_structured):
    client = _get_client()
    context = f"Задача структурированная.\nОписание: {task_description}" if is_structured else f"Задача: {task_name}"
    prompt = f"""Анализируй фидбэк сотрудника.

{context}
Фидбэк: "{feedback_text}"

Верни JSON:
{{"score": 1-5, "is_adequate": true/false, "summary": "резюме", "has_blockers": true/false, "blockers": "описание или null", "recommendation": "рекомендация"}}

Только JSON."""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}]
    )
    try:
        return json.loads(response.content[0].text)
    except Exception:
        return {"score": 0, "is_adequate": False, "summary": feedback_text, "has_blockers": False}

async def generate_weekly_report(tasks_data, employee_name):
    client = _get_client()
    tasks_json = json.dumps(tasks_data, ensure_ascii=False, indent=2)
    prompt = f"""Составь еженедельный отчёт для сотрудника {employee_name}.

Задачи: {tasks_json}

Верни JSON:
{{"detailed": "подробный отчёт markdown", "summary": "краткий 3-5 строк", "overall_score": 1-10, "completed_tasks": 0, "pending_tasks": 0}}

Только JSON."""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )
    try:
        return json.loads(response.content[0].text)
    except Exception:
        return {"detailed": "Ошибка", "summary": "Ошибка", "overall_score": 0}
