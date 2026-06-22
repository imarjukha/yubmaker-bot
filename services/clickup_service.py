import httpx
from datetime import datetime
from config import CLICKUP_API_TOKEN, CLICKUP_LIST_ID, TEAM_MAP

BASE_URL = "https://api.clickup.com/api/v2"
HEADERS = {
    "Authorization": CLICKUP_API_TOKEN,
    "Content-Type": "application/json"
}


async def create_task(
    name: str,
    description: str,
    priority: str,
    assignee_username: str | None,
    subtasks: list[str] | None = None
) -> dict | None:
    """Создаёт задачу в ClickUp и возвращает её данные."""

    priority_map = {"urgent": 1, "high": 2, "normal": 3, "low": 4}

    payload = {
        "name": name,
        "description": description,
        "priority": priority_map.get(priority, 3),
    }

    # Назначаем исполнителя если есть
    if assignee_username and assignee_username in TEAM_MAP:
        payload["assignees"] = [TEAM_MAP[assignee_username]]

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/list/{CLICKUP_LIST_ID}/task",
            headers=HEADERS,
            json=payload
        )

        if response.status_code != 200:
            return None

        task = response.json()
        task_id = task["id"]

        # Создаём подзадачи если есть
        if subtasks:
            for subtask_name in subtasks:
                await client.post(
                    f"{BASE_URL}/list/{CLICKUP_LIST_ID}/task",
                    headers=HEADERS,
                    json={"name": subtask_name, "parent": task_id}
                )

        return task


async def get_task(task_id: str) -> dict | None:
    """Получает задачу по ID."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}/task/{task_id}",
            headers=HEADERS
        )
        return response.json() if response.status_code == 200 else None


async def update_task_assignee(task_id: str, clickup_user_id: int) -> bool:
    """Назначает исполнителя на задачу."""
    async with httpx.AsyncClient() as client:
        response = await client.put(
            f"{BASE_URL}/task/{task_id}",
            headers=HEADERS,
            json={"assignees": {"add": [clickup_user_id], "rem": []}}
        )
        return response.status_code == 200


async def get_tasks_for_user(clickup_user_id: int, due_date_from: datetime = None) -> list[dict]:
    """Получает задачи сотрудника за период."""
    params = {
        "assignees[]": [clickup_user_id],
        "include_closed": True,
        "subtasks": True,
    }
    if due_date_from:
        params["due_date_gt"] = int(due_date_from.timestamp() * 1000)

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}/list/{CLICKUP_LIST_ID}/task",
            headers=HEADERS,
            params=params
        )

        if response.status_code != 200:
            return []

        return response.json().get("tasks", [])


async def add_task_comment(task_id: str, comment: str) -> bool:
    """Добавляет комментарий к задаче (для сохранения фидбэка)."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/task/{task_id}/comment",
            headers=HEADERS,
            json={"comment_text": comment, "notify_all": False}
        )
        return response.status_code == 200
