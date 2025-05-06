from motor.motor_asyncio import AsyncIOMotorClient

from core.config.config import settings

motor_client = AsyncIOMotorClient(settings.db_url)
