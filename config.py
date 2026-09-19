from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = [int(value.strip()) for value in os.getenv("ADMIN_IDS", "").split(",") if value.strip()]
CHANNEL_DEST = os.getenv("CHANNEL_DEST", "").strip()
DATABASE_PATH = os.getenv("DATABASE_PATH", str(Path(__file__).with_name("shop.db")))

# Стоимость указана в звёздах Telegram.
DELIVERY_METHODS = {
    "pickup": {"name": "Самовывоз", "cost": 0},
    "courier": {"name": "Курьер по городу", "cost": 50},
    "post": {"name": "Почта России / СДЭК", "cost": 100},
}
