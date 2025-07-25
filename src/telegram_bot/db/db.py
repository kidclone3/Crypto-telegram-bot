from motor.motor_asyncio import AsyncIOMotorClient

from telegram_bot.core.config import settings


motor_client = AsyncIOMotorClient(settings.db_url)
