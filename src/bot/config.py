"""
Configuration settings for Postbot.
Loads settings from environment variables using python-dotenv.
"""
import os
from pathlib import Path
from typing import List
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "").strip()
MONGO_URI: str = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DATABASE_NAME: str = os.getenv("DATABASE_NAME", "postbot")
DATABASE_PATH: str = os.getenv("DATABASE_PATH", str(BASE_DIR / "data" / "postbot.db"))
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

def _parse_owner_ids(raw_ids: str) -> List[int]:
    ids: List[int] = []
    if not raw_ids:
        return ids
    for part in raw_ids.replace(";", ",").split(","):
        cleaned = part.strip()
        if cleaned.isdigit() or (cleaned.startswith("-") and cleaned[1:].isdigit()):
            ids.append(int(cleaned))
    return ids

OWNER_IDS: List[int] = _parse_owner_ids(os.getenv("OWNER_IDS", ""))
