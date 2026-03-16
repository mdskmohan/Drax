"""
Telegram webhook endpoint for FastAPI.
"""
import logging
from fastapi import APIRouter, Request, HTTPException, status
from telegram import Update

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/webhook")
async def telegram_webhook(request: Request):
    """Receive and process Telegram webhook updates."""
    from app.main import application  # avoid circular import

    try:
        data = await request.json()
        update = Update.de_json(data, application.bot)
        await application.process_update(update)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/health")
async def health_check():
    """
    Real health check — verifies database and Redis connectivity.
    Returns 200 only if all critical dependencies are reachable.
    """
    from app.database import engine
    from app.config import settings
    checks = {}

    # Database
    try:
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        logger.error(f"Health check: DB unreachable: {e}")
        checks["database"] = "error"

    # Redis (via Celery broker URL)
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(settings.redis_url, socket_connect_timeout=2)
        await r.ping()
        await r.aclose()
        checks["redis"] = "ok"
    except Exception as e:
        logger.error(f"Health check: Redis unreachable: {e}")
        checks["redis"] = "error"

    all_ok = all(v == "ok" for v in checks.values())
    http_status = status.HTTP_200_OK if all_ok else status.HTTP_503_SERVICE_UNAVAILABLE
    from fastapi.responses import JSONResponse
    return JSONResponse(
        content={"status": "healthy" if all_ok else "degraded", "service": "Drax", "checks": checks},
        status_code=http_status,
    )
