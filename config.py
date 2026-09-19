from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = [int(value.strip()) for value in os.getenv("ADMIN_IDS", "").split(",") if value.strip()]
CHANNEL_DEST = os.getenv("CHANNEL_DEST", "").strip()
DATABASE_PATH = os.getenv("DATABASE_PATH", str(Path(__file__).with_name("shop.db")))
CARD_NUMBER = os.getenv("CARD_NUMBER", "").strip()
CARD_HOLDER = os.getenv("CARD_HOLDER", "").strip()
CARD_BANK = os.getenv("CARD_BANK", "").strip()

# Стоимость указана в звёздах Telegram.
DELIVERY_METHODS = {
    "pickup": {"name": "Самовывоз", "cost_uah": 0, "cost_stars": 0},
    "courier": {"name": "Курьер по городу", "cost_uah": 50, "cost_stars": 50},
    "post": {"name": "Почта / доставка", "cost_uah": 100, "cost_stars": 100},
}
