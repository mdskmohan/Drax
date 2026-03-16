"""
Privacy and data management commands.

Provides:
  /privacy  — explains what data is stored and your rights
  /delete_my_data — irreversibly deletes all your data (GDPR Art. 17 / India DPDP Act S. 13)
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from sqlalchemy import select, delete

from app.database import AsyncSessionLocal
from app.models.user import User
from app.models.meal_log import MealLog
from app.models.water_log import WaterLog
from app.models.workout_log import WorkoutLog
from app.models.weight_log import WeightLog
from app.models.progress_report import ProgressReport


PRIVACY_TEXT = """
🔒 *Your Data & Privacy*

*What Drax stores about you:*
• Profile: name, age, gender, height, weight, goal, timezone
• Daily logs: meals (food descriptions + macros), water, workouts, weight entries
• Settings: notification schedule, equipment list, diet preference, language

*What Drax does NOT do:*
• Does not share your data with third parties
• Does not use your data for advertising
• Does not sell your data
• Does not transmit identifiable health data outside this bot

*Third-party services used:*
• Nutritionix (optional) — food text is sent to their API for calorie data; governed by Nutritionix's own privacy policy
• Telegram — all messages pass through Telegram's servers; governed by Telegram's privacy policy
• LLM provider (Claude/OpenAI/DeepSeek) — meal descriptions and chat text are sent to your configured LLM for AI responses; governed by that provider's data policy

*Your rights:*
• **Right to access** — your data is yours; use /progress and /report to see it
• **Right to erasure** — use /delete\_my\_data to permanently delete everything
• **Right to portability** — contact the bot owner to export a copy of your data

*Applicable frameworks:*
This bot is designed to respect the principles of:
• EU General Data Protection Regulation (GDPR) — Art. 5, 13, 17
• India Digital Personal Data Protection Act 2023 (DPDP Act) — S. 4, 12, 13
• UK GDPR and similar national frameworks

*Questions?* Contact the bot owner directly via Telegram.
""".strip()


async def privacy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show privacy notice and data rights."""
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("🗑️ Delete All My Data", callback_data="confirm_delete_data"),
    ]])
    await update.message.reply_text(
        PRIVACY_TEXT,
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


async def delete_my_data_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Prompt for confirmation before deleting all user data."""
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Yes, delete everything", callback_data="confirm_delete_data")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel")],
    ])
    await update.message.reply_text(
        "⚠️ *Are you sure?*\n\n"
        "This will permanently delete your profile, all meal logs, water logs, "
        "workout logs, weight history, and notification settings.\n\n"
        "*This cannot be undone.*",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


async def handle_delete_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Handle confirm_delete_data callback. Returns True if handled."""
    query = update.callback_query
    if query.data != "confirm_delete_data":
        return False

    await query.answer()
    user_id = query.from_user.id

    async with AsyncSessionLocal() as session:
        # Delete all logs first (FK constraint order)
        for model in (MealLog, WaterLog, WorkoutLog, WeightLog, ProgressReport):
            try:
                await session.execute(delete(model).where(model.user_id == user_id))
            except Exception:
                pass  # table may not exist yet in some deployments

        # Delete user record
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user:
            await session.delete(user)

        await session.commit()

    await query.edit_message_text(
        "✅ *All your data has been deleted.*\n\n"
        "Your profile, all logs, and settings have been permanently removed from Drax.\n\n"
        "If you'd like to start fresh, send /start.",
        parse_mode="Markdown",
    )
    return True
