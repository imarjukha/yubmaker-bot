import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
CLICKUP_API_TOKEN = os.getenv("CLICKUP_API_TOKEN")
CLICKUP_LIST_ID = os.getenv("CLICKUP_LIST_ID", "901217527946")

TEAM_MAP = {
    "zelemash": 99761884,
    "heyannett": 99761883,
    "volgatheocean": 99763886,
    "westcost777": 99761882,
    "rinaa_k": 99844168,
    "z_polli": 99761939,
    "panchenko_tv": 99763894,
    "asti_kh": 99761885,
}

CLICKUP_TO_TELEGRAM = {
    99761884: "zelemash",
    99761883: "heyannett",
    99763886: "volgatheocean",
    99761882: "westcost777",
    99844168: "rinaa_k",
    99761939: "z_polli",
    99763894: "panchenko_tv",
    99761885: "asti_kh",
}

FEEDBACK_SCHEDULE = {
    "short": {"max_days": 7, "checkpoints": []},
    "medium": {"max_days": 14, "checkpoints": [0.5]},
    "long": {"max_days": None, "checkpoints_every": 5},
}

# redeploy 2026-06-25T18:03:53.817028
