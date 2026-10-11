import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware

from app.api.error_handlers import register_error_handlers
from app.api.v1.endpoints import auth, briefs, health, live, map, notifications, pipeline, read, tenders
from app.core.config import settings
from app.core.container import Container
from app.core.database import init_db
from app.services.live_relay import LiveEventRelay


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(level=logging.INFO)
    for name in ("httpx", "httpx2"):  # request URLs can carry secrets
        logging.getLogger(name).setLevel(logging.WARNING)
    init_db()
    app.state.container = Container(settings)
    app.state.relay = LiveEventRelay(settings.database_url)
    app.state.relay.start(asyncio.get_running_loop())
    yield
    app.state.relay.stop()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(GZipMiddleware, minimum_size=1000)  # map GeoJSON ~1 MB raw -> ~300 KB
register_error_handlers(app)
app.include_router(health.router)
app.include_router(pipeline.router)
app.include_router(map.router)
app.include_router(read.router)
app.include_router(live.router)
app.include_router(tenders.router)
app.include_router(auth.router)
app.include_router(notifications.router)
app.include_router(briefs.router)
