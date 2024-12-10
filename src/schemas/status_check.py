from pydantic import BaseModel

from src.models import LoginStatus


class StausCheck(BaseModel):
    status: LoginStatus
