"""
Cuisine preference handler.
/cuisine — pick a cuisine style for all meal plans (Mediterranean, Indian, Japanese, etc.)
"""
from telegram import Update
from telegram.ext import ContextTypes
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.user import User
from app.bot.keyboards import cuisine_keyboard, main_menu_keyboard

_CUISINE_LABELS = {
    "mediterranean": "🌊 Mediterranean",
    "indian":        "🇮🇳 Indian",
    "japanese":      "🇯🇵 Japanese",
    "mexican":       "🇲🇽 Mexican",
    "italian":       "🇮🇹 Italian",
    "chinese":       "🇨🇳 Chinese",
    "general":       "🌍 General (no preference)",
}


async def cuisine_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show cuisine preference picker."""
    query = update.callback_query
    user_id = update.effective_user.id if not query else query.from_user.id

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            txt = "Please /start first."
            if query:
                await query.answer(txt, show_alert=True)
            else:
                await update.message.reply_text(txt)
            return

    current = getattr(user, "cuisine_preference", None)
    current_label = _CUISINE_LABELS.get(current or "general", "General")
    msg = (
        f"🍽️ *Meal Plan Cuisine*\n\n"
        f"Current: *{current_label}*\n\n"
        "Choose your preferred cuisine style — all daily plans and meal suggestions "
        "will use this style.\n"
        "_You can change this anytime._"
    )
    if query:
        await query.answer()
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=cuisine_keyboard(current))
    else:
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=cuisine_keyboard(current))


async def handle_cuisine_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Handle cuisine_* callbacks. Returns True if handled."""
    query = update.callback_query
    if not query.data.startswith("cuisine_"):
        return False

    await query.answer()
    cuisine = query.data.replace("cuisine_", "")
    user_id = query.from_user.id

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            return True
        user.cuisine_preference = None if cuisine == "general" else cuisine
        await session.commit()

    label = _CUISINE_LABELS.get(cuisine, cuisine.capitalize())
    await query.edit_message_text(
        f"✅ *Cuisine set to {label}!*\n\n"
        "Your meal plans and daily plan will now follow this style. "
        "Use /plan to get today's updated meal plan.",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )
    return True
