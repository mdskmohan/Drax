"""
Progress tracking handlers — weight logs, weekly reports, goal tracking.
"""
from datetime import datetime, timezone, timedelta
from telegram import Update
from telegram.ext import ContextTypes
from sqlalchemy import select, func

from app.database import AsyncSessionLocal
from app.models.user import User
from app.models.weight_log import WeightLog
from app.models.meal_log import MealLog
from app.models.water_log import WaterLog
from app.models.workout_log import WorkoutLog
from app.agents.progress_agent import ProgressAgent
from app.graph import drax_graph
from app.bot.keyboards import main_menu_keyboard
from app.bot.handlers.parsers import parse_weight_kg


progress_agent = ProgressAgent()  # kept for generate_weekly_report


async def log_weight_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Prompt for weight entry."""
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text(
            "⚖️ *Log Your Weight*\n\n"
            "Enter your current weight:\n\n"
            "_e.g., 89.5kg or 197 lbs_",
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(
            "⚖️ *Log Your Weight*\n\nEnter your weight (e.g., 89.5kg or 197 lbs):",
            parse_mode="Markdown",
        )
    context.user_data["awaiting_weight"] = True


async def process_weight_log(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Process weight log entry via LangGraph."""
    if not context.user_data.get("awaiting_weight"):
        return False

    text = update.message.text.strip()
    user_id = update.effective_user.id
    context.user_data.pop("awaiting_weight", None)

    # Normalise lbs → kg before passing to graph
    kg, label = parse_weight_kg(text)
    graph_input = f"{kg} kg" if kg else text

    processing_msg = await update.message.reply_text("⚖️ Logging your weight...")

    result = await drax_graph.ainvoke({
        "user_id": user_id,
        "user_input": graph_input,
        "intent": "log_weight",
    })

    response = result.get("response", "⚖️ Weight logged!")
    if len(response) > 4000:
        response = response[:4000] + "..."

    await processing_msg.edit_text(
        response,
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )
    return True


async def show_progress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show overall progress summary via LangGraph."""
    query = update.callback_query
    user_id = update.effective_user.id if not query else query.from_user.id

    if query:
        await query.answer()
        msg = await query.edit_message_text("📊 Loading your progress...")
    else:
        msg = await update.message.reply_text("📊 Loading your progress...")

    result = await drax_graph.ainvoke({
        "user_id": user_id,
        "user_input": "show my progress",
        "intent": "get_progress",
    })

    response = result.get("response", "📊 Could not load progress. Try again.")
    if len(response) > 4000:
        response = response[:4000] + "..."

    await msg.edit_text(
        response,
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )


async def generate_weekly_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate and send the weekly progress report."""
    user_id = update.effective_user.id
    msg = await update.message.reply_text("📊 Generating your weekly report...")

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            return

        seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)

        # Fetch all week data — order_by ensures correct chronological trend analysis
        weights = (await session.execute(
            select(WeightLog).where(WeightLog.user_id == user_id)
            .where(WeightLog.logged_at >= seven_days_ago)
            .order_by(WeightLog.logged_at)
        )).scalars().all()

        meals = (await session.execute(
            select(MealLog).where(MealLog.user_id == user_id)
            .where(MealLog.logged_at >= seven_days_ago)
            .order_by(MealLog.logged_at)
        )).scalars().all()

        workouts = (await session.execute(
            select(WorkoutLog).where(WorkoutLog.user_id == user_id)
            .where(WorkoutLog.created_at >= seven_days_ago)
            .order_by(WorkoutLog.created_at)
        )).scalars().all()

        waters = (await session.execute(
            select(WaterLog).where(WaterLog.user_id == user_id)
            .where(WaterLog.logged_at >= seven_days_ago)
            .order_by(WaterLog.logged_at)
        )).scalars().all()

        week_data = {
            "weight_logs": [{"weight_kg": w.weight_kg, "logged_at": str(w.logged_at)} for w in weights],
            "meal_logs": [{"calories": m.calories, "protein_g": m.protein_g} for m in meals],
            "workout_logs": [{"completed": w.completed, "workout_type": w.workout_type} for w in workouts],
            "water_logs": [{"amount_ml": w.amount_ml} for w in waters],
        }

        report = await progress_agent.generate_weekly_report(user, week_data)

        if len(report) > 4000:
            report = report[:4000] + "...\n\n_[Report truncated]_"

        await msg.edit_text(report, parse_mode="Markdown", reply_markup=main_menu_keyboard())
