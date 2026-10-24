from __future__ import annotations
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
load_dotenv(ROOT / ".env")
TOKEN = os.getenv("DISCORD_TOKEN", "").strip()
APP_DB = DATA_DIR / "420vault.db"
DEFAULT_VAULT = ROOT / "vault"
