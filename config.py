import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
CLICKUP_API_TOKEN = os.getenv("CLICKUP_API_TOKEN")
CLICKUP_LIST_ID = os.getenv("CLICKUP_LIST_ID", "901217527946")  # DCT Operations

# Telegram user_id → ClickUp user_id
# Заполни после того как узнаешь Telegram ID каждого сотрудника
TEAM_MAP = {
    TEAM_MAP = {
    "Zelemash": 99761884,
    "heyannett": 99761883,
    "volgatheocean": 99763886,
    "westcost777": 99761882,
    "rinaa_k": 99844168,
    "Asti_Kh": 99761885,
    "z_polli": 99761939,
    "panchenko_tv": 99763894,
}

CLICKUP_TO_TELEGRAM = {
    99761884: "Zelemash",
    99761883: "heyannett",
    99763886: "volgatheocean",
    99761882: "westcost777",
    99844168: "rinaa_k",
    99761885: "Asti_Kh",
    99761939: "z_polli",
    99763894: "panchenko_tv",
}
}

# ClickUp user_id → Telegram username (для личных сообщений)
CLICKUP_TO_TELEGRAM = {
    # clickup_user_id: "telegram_username"
    # Пример: 99761883: "anna_smirnova"
}

# Периоды фидбэка (в днях)
FEEDBACK_SCHEDULE = {
    "short": {"max_days": 7, "checkpoints": []},           # < 1 нед → только в конце
    "medium": {"max_days": 14, "checkpoints": [0.5]},      # 1-2 нед → посередине
    "long": {"max_days": None, "checkpoints_every": 5},    # > 2 нед → каждые 5 дней
}
