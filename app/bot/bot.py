"""
Main Telegram Bot Application.
Registers all handlers and sets up the application.
"""
import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

from app.config import settings
from app.bot.handlers.onboarding import (
    start_command,
    handle_onboarding_message,
    handle_onboarding_callback,
)
from app.bot.handlers.meals import (
    log_meal_start,
    meal_type_selected,
    process_meal_text,
    process_meal_photo,
    show_todays_meals,
)
from app.bot.handlers.water import (
    log_water_start,
    water_amount_callback,
    process_water_text,
    show_water_status,
)
from app.bot.handlers.workouts import (
    show_todays_workout,
    workout_completion_callback,
    process_pain_report,
)
from app.bot.handlers.progress import (
    log_weight_start,
    process_weight_log,
    show_progress,
    generate_weekly_report,
)
from app.bot.handlers.general import (
    help_command,
    menu_command,
    daily_plan_command,
    motivation_command,
    unknown_message_handler,
)

logger = logging.getLogger(__name__)


async def route_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Central router for all text messages.
    Checks in-progress states first, then falls through to handlers.
    """
    # Onboarding check
    from sqlalchemy import select
    from app.database import AsyncSessionLocal
    from app.models.user import User, OnboardingState

    user_id = update.effective_user.id
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user and user.onboarding_state != OnboardingState.completed:
            handled = await handle_onboarding_message(update, context)
            if handled:
                return

    # State-based routing
    if await process_weight_log(update, context):
        return
    if await process_water_text(update, context):
        return
    if await process_meal_text(update, context):
        return
    if await process_pain_report(update, context):
        return

    # Fallback
    await unknown_message_handler(update, context)


async def route_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Central callback query router."""
    query = update.callback_query
    data = query.data

    # Onboarding callbacks
    if data.startswith(("gender_", "diet_", "level_", "gym_")):
        await handle_onboarding_callback(update, context)
        return

    # Main menu
    if data == "log_meal":
        await log_meal_start(update, context)
    elif data == "log_water":
        await log_water_start(update, context)
    elif data == "todays_workout":
        await show_todays_workout(update, context)
    elif data == "log_weight":
        await log_weight_start(update, context)
    elif data == "my_progress":
        await show_progress(update, context)
    elif data == "daily_plan":
        await daily_plan_command(update, context)
    elif data == "motivation":
        await motivation_command(update, context)

    # Meal type selection
    elif data.startswith("meal_"):
        await meal_type_selected(update, context)

    # Water quick log
    elif data.startswith("water_"):
        await water_amount_callback(update, context)

    # Workout completion
    elif data.startswith("workout_"):
        await workout_completion_callback(update, context)

    # Cancel
    elif data == "cancel":
        await query.answer()
        from app.bot.keyboards import main_menu_keyboard
        await query.edit_message_text("Cancelled. What else can I help you with?", reply_markup=main_menu_keyboard())

    else:
        await query.answer("Option not recognized")


def build_application() -> Application:
    """Build and configure the Telegram Application."""
    app = Application.builder().token(settings.telegram_bot_token).build()

    # Commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("menu", menu_command))
    app.add_handler(CommandHandler("plan", daily_plan_command))
    app.add_handler(CommandHandler("meal", log_meal_start))
    app.add_handler(CommandHandler("water", log_water_start))
    app.add_handler(CommandHandler("workout", show_todays_workout))
    app.add_handler(CommandHandler("weight", log_weight_start))
    app.add_handler(CommandHandler("progress", show_progress))
    app.add_handler(CommandHandler("report", generate_weekly_report))
    app.add_handler(CommandHandler("motivation", motivation_command))

    # Photos (food photos)
    app.add_handler(MessageHandler(filters.PHOTO, process_meal_photo))

    # All text messages go through central router
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, route_text_message))

    # All callback queries
    app.add_handler(CallbackQueryHandler(route_callback))

    return app
