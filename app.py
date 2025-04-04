import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.routers import main_router
from src.core.errors import ValidationException


app = FastAPI()
app.include_router(main_router)


@app.exception_handler(ValidationException)
async def validation_exception_handler(request: Request, exc: ValidationException):
    return JSONResponse(
        status_code=exc.http_status_code,
        content={
            "status_code": exc.http_status_code,
            "details": exc.details,
        },
    )
