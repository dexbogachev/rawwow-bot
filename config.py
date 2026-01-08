import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Config:
    bot_token: str
    admin_ids: set[int]

def load_config() -> Config:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN is empty. Set it in .env")

    raw_admins = os.getenv("ADMIN_IDS", "").strip()
    admin_ids = set()
    if raw_admins:
        admin_ids = {int(x.strip()) for x in raw_admins.split(",") if x.strip().isdigit()}

    return Config(bot_token=token, admin_ids=admin_ids)
