"""
Drax — FastAPI Application Entry Point.
Handles webhook registration, database init, and Telegram bot lifecycle.
"""
import asyncio
import logging
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.config import settings
from app.database import init_db
from app.bot.bot import build_application

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── Telegram Application (global) ──────────────────────────────────────────────
application = build_application()


# ── FastAPI Lifespan ───────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    logger.info("Starting Drax...")

    # Init database
    await init_db()
    logger.info("Database initialized")

    # Initialize Telegram app
    await application.initialize()
    await application.start()

    # Set webhook if URL is configured
    if settings.telegram_webhook_url:
        webhook_url = f"{settings.telegram_webhook_url}/webhook"
        await application.bot.set_webhook(url=webhook_url)
        logger.info(f"Webhook set to: {webhook_url}")
    else:
        logger.warning("No TELEGRAM_WEBHOOK_URL set — run in polling mode instead")

    # Start in-process scheduler (handles notifications without Celery)
    from app.tasks.scheduled import async_scheduler_loop
    scheduler_task = asyncio.create_task(async_scheduler_loop())
    logger.info("In-process notification scheduler started")

    logger.info("Drax is live! 💪")
    yield

    # Shutdown
    scheduler_task.cancel()
    logger.info("Shutting down Drax...")
    await application.stop()
    await application.shutdown()


# ── FastAPI App ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Drax API",
    description="AI Personal Fitness Coach via Telegram",
    version="1.0.0",
    lifespan=lifespan,
)

# Register routes
from app.api.webhook import router as webhook_router  # noqa
from app.api.health_sync_api import router as health_sync_router  # noqa
app.include_router(webhook_router)
app.include_router(health_sync_router)


@app.get("/")
async def root():
    return {
        "service": "Drax",
        "status": "running",
        "description": "AI Personal Fitness Coach — Telegram Bot",
    }
