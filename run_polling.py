"""
Run the bot in polling mode (for local development — no webhook needed).
Use this instead of the FastAPI server when testing locally.
"""
import asyncio
import logging
from app.config import settings
from app.database import init_db
from app.bot.bot import build_application

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    logger.info("Initializing database...")
    await init_db()

    logger.info("Starting Drax in polling mode...")
    app = build_application()

    async with app:
        await app.start()
        logger.info("Drax is running! Send /start to your bot on Telegram.")
        await app.updater.start_polling(drop_pending_updates=True)

        # Start in-process scheduler so notifications fire without Celery
        from app.tasks.scheduled import async_scheduler_loop
        scheduler_task = asyncio.create_task(async_scheduler_loop())
        logger.info("In-process notification scheduler started")

        try:
            await app.updater.idle()
        finally:
            scheduler_task.cancel()

        await app.stop()


if __name__ == "__main__":
    asyncio.run(main())
