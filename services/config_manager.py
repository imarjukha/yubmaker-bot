"""
Динамическое управление пользователями.
Хранит пользователей в data/users.json поверх базового config.py
"""
import json
from pathlib import Path
from config import TEAM_MAP as BASE_TEAM_MAP, CLICKUP_TO_TELEGRAM as BASE_CLICKUP_TO_TELEGRAM

USERS_FILE = Path("data/users.json")


def _load_users() -> dict:
    if not USERS_FILE.exists():
        USERS_FILE.parent.mkdir(exist_ok=True)
        return {}
    with open(USERS_FILE) as f:
        return json.load(f)


def _save_users(users: dict):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


def get_team_map() -> dict:
    """Возвращает объединённый TEAM_MAP (базовый + динамические)."""
    users = _load_users()
    result = dict(BASE_TEAM_MAP)
    result.update(users.get("team_map", {}))
    return result


def get_clickup_to_telegram() -> dict:
    """Возвращает объединённый CLICKUP_TO_TELEGRAM."""
    users = _load_users()
    result = dict(BASE_CLICKUP_TO_TELEGRAM)
    result.update({int(k): v for k, v in users.get("clickup_to_telegram", {}).items()})
    return result


def add_user(username: str, clickup_id: int):
    users = _load_users()
    if "team_map" not in users:
        users["team_map"] = {}
    if "clickup_to_telegram" not in users:
        users["clickup_to_telegram"] = {}
    users["team_map"][username.lower()] = clickup_id
    users["clickup_to_telegram"][str(clickup_id)] = username.lower()
    _save_users(users)


def remove_user(username: str) -> bool:
    users = _load_users()
    username = username.lower()
    found = False
    if username in users.get("team_map", {}):
        clickup_id = users["team_map"].pop(username)
        users.get("clickup_to_telegram", {}).pop(str(clickup_id), None)
        found = True
    # Также проверяем базовый конфиг
    elif username in BASE_TEAM_MAP:
        if "removed" not in users:
            users["removed"] = []
        users["removed"].append(username)
        found = True
    _save_users(users)
    return found


def list_users() -> dict:
    return get_team_map()
