"""
config.py
---------
Centralized configuration loader for the Short Squeeze Bot.

Loads:
- Secrets from .env (Telegram tokens, API keys)
- Strategy settings from settings.yaml

Everywhere else in the code imports from here, so we never
hardcode tokens or magic numbers in our logic.
"""

import os
from pathlib import Path
import yaml
from dotenv import load_dotenv

# ---------------------------------------------------------------
# Locate the project root (one folder up from src/)
# ---------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------
# Load secrets from .env
# ---------------------------------------------------------------
load_dotenv(PROJECT_ROOT / ".env")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
SCRAPERAPI_KEY = os.getenv("SCRAPERAPI_KEY")

# Fail loudly if Telegram secrets are missing
if not TELEGRAM_BOT_TOKEN:
    raise ValueError(
        "TELEGRAM_BOT_TOKEN is missing in .env file. "
        "Open .env and add: TELEGRAM_BOT_TOKEN=your_token_here"
    )
if not TELEGRAM_CHAT_ID:
    raise ValueError(
        "TELEGRAM_CHAT_ID is missing in .env file. "
        "Open .env and add: TELEGRAM_CHAT_ID=your_chat_id_here"
    )

# ScraperAPI is optional — we warn but don't crash if missing
# (in production on cloud servers, it may not be needed)

# ---------------------------------------------------------------
# Load strategy settings from settings.yaml
# ---------------------------------------------------------------
SETTINGS_FILE = PROJECT_ROOT / "settings.yaml"

with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
    SETTINGS = yaml.safe_load(f)

# Expose individual sections for convenience
STRATEGY = SETTINGS["strategy"]
HALAL = SETTINGS["halal"]
SCHEDULE = SETTINGS["schedule"]
OUTPUT = SETTINGS["output"]