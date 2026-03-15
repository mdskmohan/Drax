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
    return {"status": "healthy", "service": "Drax"}
