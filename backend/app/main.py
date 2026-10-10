import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.error_handlers import register_error_handlers
from app.api.v1.endpoints import health, pipeline
from app.core.config import settings
from app.core.container import Container
from app.core.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(level=logging.INFO)
    for name in ("httpx", "httpx2"):  # request URLs can carry secrets
        logging.getLogger(name).setLevel(logging.WARNING)
    init_db()
    app.state.container = Container(settings)
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
register_error_handlers(app)
app.include_router(health.router)
app.include_router(pipeline.router)
