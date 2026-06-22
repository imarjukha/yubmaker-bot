import json
import os
from datetime import datetime
from pathlib import Path

STORAGE_FILE = Path("data/storage.json")


def _load() -> dict:
    if not STORAGE_FILE.exists():
        STORAGE_FILE.parent.mkdir(exist_ok=True)
        return {"pending_assignments": {}, "active_tasks": {}, "feedback_sessions": {}}
    with open(STORAGE_FILE) as f:
        return json.load(f)


def _save(data: dict):
    with open(STORAGE_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)


def save_pending_assignment(message_id: int, task_data: dict):
    """Сохраняет задачу ожидающую назначения исполнителя."""
    data = _load()
    data["pending_assignments"][str(message_id)] = task_data
    _save(data)


def get_pending_assignment(message_id: int) -> dict | None:
    data = _load()
    return data["pending_assignments"].get(str(message_id))


def remove_pending_assignment(message_id: int):
    data = _load()
    data["pending_assignments"].pop(str(message_id), None)
    _save(data)


def save_active_task(task_id: str, task_info: dict):
    """Сохраняет активную задачу с расписанием фидбэка."""
    data = _load()
    data["active_tasks"][task_id] = {
        **task_info,
        "created_at": datetime.now().isoformat(),
        "feedbacks": []
    }
    _save(data)


def get_active_tasks() -> dict:
    return _load().get("active_tasks", {})


def add_feedback_to_task(task_id: str, feedback: dict):
    data = _load()
    if task_id in data["active_tasks"]:
        data["active_tasks"][task_id]["feedbacks"].append({
            **feedback,
            "timestamp": datetime.now().isoformat()
        })
        _save(data)


def save_feedback_session(user_id: int, session: dict):
    """Сохраняет активную сессию фидбэка для пользователя."""
    data = _load()
    data["feedback_sessions"][str(user_id)] = session
    _save(data)


def get_feedback_session(user_id: int) -> dict | None:
    data = _load()
    return data["feedback_sessions"].get(str(user_id))


def clear_feedback_session(user_id: int):
    data = _load()
    data["feedback_sessions"].pop(str(user_id), None)
    _save(data)
