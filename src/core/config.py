from pathlib import Path

from pydantic import ConfigDict
from pydantic_settings import BaseSettings

BASE_DIR = Path(__name__).parent.parent.parent.resolve()
MESSAGE_LIMIT = 50


class Config(BaseSettings):
    model_config = ConfigDict(env_file=".env", extra="allow")
    api_id: int
    api_hash: str
    bot_token: str
    db_url: str


settings = Config()
