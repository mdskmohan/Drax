"""
Apple Health / Android Health Connect sync.
Generates a personal webhook URL + token for each user.
iOS Shortcuts and Android apps can POST health data to this URL.
"""
import secrets
from datetime import datetime, timezone
from telegram import Update
from telegram.ext import ContextTypes
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.user import User
from app.config import settings
from app.bot.keyboards import health_sync_keyboard, main_menu_keyboard


async def sync_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show health sync options."""
    query = update.callback_query
    if query:
        await query.answer()
        msg_fn = query.edit_message_text
    else:
        msg_fn = update.message.reply_text

    await msg_fn(
        "📱 *Health Sync*\n\n"
        "Connect Drax to Apple Health or Android Health Connect to automatically sync:\n"
        "• Weight from your phone\n"
        "• Step count\n"
        "• Active calories burned\n\n"
        "Choose your platform:",
        parse_mode="Markdown",
        reply_markup=health_sync_keyboard(),
    )


async def sync_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle sync platform selection."""
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data == "sync_token":
        token = await _get_or_create_token(user_id)
        base_url = settings.telegram_webhook_url or "https://your-drax-instance.com"
        sync_url = f"{base_url}/sync/{token}"
        await query.edit_message_text(
            f"🔗 *Your Personal Sync URL*\n\n"
            f"`{sync_url}`\n\n"
            f"Use this URL in your iOS Shortcut or Android automation.\n\n"
            f"POST JSON to this URL:\n"
            f"`{{\"type\": \"weight\", \"value\": 85.5}}`\n"
            f"`{{\"type\": \"steps\", \"value\": 8000}}`\n"
            f"`{{\"type\": \"calories_burned\", \"value\": 450}}`\n\n"
            f"⚠️ Keep this URL private — it's your personal access token.",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(),
        )

    elif data == "sync_apple":
        token = await _get_or_create_token(user_id)
        base_url = settings.telegram_webhook_url or "https://your-drax-instance.com"
        sync_url = f"{base_url}/sync/{token}"
        await query.edit_message_text(
            f"📱 *Apple Health Setup (iOS Shortcuts)*\n\n"
            f"**Step 1:** Open the *Shortcuts* app on your iPhone\n\n"
            f"**Step 2:** Create a new Automation → *Health* → *Body Weight* → *Any Change*\n\n"
            f"**Step 3:** Add action → *Get Health Samples* (Body Mass)\n\n"
            f"**Step 4:** Add action → *URL* → paste:\n`{sync_url}`\n\n"
            f"**Step 5:** Add action → *Get Contents of URL*\n"
            f"• Method: POST\n"
            f"• Headers: Content-Type: application/json\n"
            f"• Body: `{{\"type\":\"weight\",\"value\":\"[Body Mass]\"}}`\n\n"
            f"**Step 6:** Save. Every time you log weight in Apple Health, Drax auto-syncs! ✅",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(),
        )

    elif data == "sync_android":
        token = await _get_or_create_token(user_id)
        base_url = settings.telegram_webhook_url or "https://your-drax-instance.com"
        sync_url = f"{base_url}/sync/{token}"
        await query.edit_message_text(
            f"🤖 *Android Health Connect Setup*\n\n"
            f"Use *Tasker* or *MacroDroid* (free apps) to sync:\n\n"
            f"**With MacroDroid:**\n"
            f"1. Create Macro → Trigger: *Webhook*\n"
            f"2. Action: *HTTP Request*\n"
            f"   URL: `{sync_url}`\n"
            f"   Method: POST\n"
            f"   Body: `{{\"type\":\"weight\",\"value\":YOUR_WEIGHT}}`\n\n"
            f"**Manual sync:** Just text Drax your weight like:\n"
            f"`I weigh 85.5kg` → logged automatically ✅\n\n"
            f"Full Health Connect API integration coming soon!",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(),
        )


async def _get_or_create_token(user_id: int) -> str:
    """Get existing sync token or create a new one for the user."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            return "no-user"
        if not user.health_sync_token:
            user.health_sync_token = secrets.token_urlsafe(32)
            await session.commit()
        return user.health_sync_token
