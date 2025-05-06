from motor.motor_asyncio import AsyncIOMotorClient

from src.core.config import settings

motor_client = AsyncIOMotorClient(settings.db_url)
