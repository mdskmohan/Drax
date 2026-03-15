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
from app.bot.keyboards import main_menu_keyboard


progress_agent = ProgressAgent()


async def log_weight_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Prompt for weight entry."""
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text(
            "⚖️ *Log Your Weight*\n\n"
            "Enter your current weight in kg:\n\n"
            "_e.g., 89.5_",
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(
            "⚖️ *Log Your Weight*\n\nEnter your weight in kg:",
            parse_mode="Markdown",
        )
    context.user_data["awaiting_weight"] = True


async def process_weight_log(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Process weight log entry."""
    if not context.user_data.get("awaiting_weight"):
        return False

    text = update.message.text.strip()
    user_id = update.effective_user.id
    context.user_data.pop("awaiting_weight", None)

    try:
        weight = float(text.replace("kg", "").strip())
        if not 30 <= weight <= 300:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Please enter a valid weight in kg (e.g., 89.5)")
        return True

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            return True

        # Get AI feedback
        feedback = await progress_agent.log_weight_feedback(user, weight)

        # Log weight
        wl = WeightLog(user_id=user_id, weight_kg=weight, ai_feedback=feedback)
        session.add(wl)

        # Update user's current weight
        old_weight = user.current_weight_kg
        user.current_weight_kg = weight
        await session.commit()

        # Build progress bar
        if user.goal_weight_kg and old_weight:
            start = max(old_weight, weight)  # use starting weight or current higher
            bar = progress_agent.build_progress_bar(weight, old_weight or weight + 1, user.goal_weight_kg)
        else:
            bar = ""

        change = (old_weight - weight) if old_weight else 0
        change_str = f"📉 -{abs(change):.1f}kg" if change > 0 else f"📈 +{abs(change):.1f}kg" if change < 0 else "= No change"

        await update.message.reply_text(
            f"⚖️ *Weight logged: {weight}kg*\n\n"
            f"{change_str} from last log\n"
            f"Goal: {user.goal_weight_kg}kg\n"
            f"Remaining: {weight - (user.goal_weight_kg or weight):.1f}kg\n\n"
            + (bar + "\n\n" if bar else "") +
            f"💬 *Coach:* _{feedback}_",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(),
        )

    return True


async def show_progress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show overall progress summary."""
    query = update.callback_query
    user_id = update.effective_user.id if not query else query.from_user.id

    if query:
        await query.answer()
        msg = await query.edit_message_text("📊 Loading your progress...")
    else:
        msg = await update.message.reply_text("📊 Loading your progress...")

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            await msg.edit_text("Please /start to set up your profile.")
            return

        # Last 7 days stats
        seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

        # Weight history
        weights_result = await session.execute(
            select(WeightLog).where(WeightLog.user_id == user_id).order_by(WeightLog.logged_at)
        )
        all_weights = weights_result.scalars().all()

        # Today's calories
        cal_result = await session.execute(
            select(func.sum(MealLog.calories))
            .where(MealLog.user_id == user_id)
            .where(MealLog.logged_at >= today_start)
        )
        today_cal = cal_result.scalar() or 0.0

        # Today's water
        water_result = await session.execute(
            select(func.sum(WaterLog.amount_ml))
            .where(WaterLog.user_id == user_id)
            .where(WaterLog.logged_at >= today_start)
        )
        today_water = water_result.scalar() or 0.0

        # Weekly workouts
        workouts_result = await session.execute(
            select(WorkoutLog)
            .where(WorkoutLog.user_id == user_id)
            .where(WorkoutLog.created_at >= seven_days_ago)
        )
        weekly_workouts = workouts_result.scalars().all()
        completed_this_week = sum(1 for w in weekly_workouts if w.completed)

        # Build response
        lost_total = (
            (all_weights[0].weight_kg - user.current_weight_kg)
            if all_weights else 0
        )
        remaining = (user.current_weight_kg or 0) - (user.goal_weight_kg or 0)

        lines = [
            f"📊 *Your Progress Dashboard*\n",
            f"━━━━━━━━━━━━━━━━",
            f"⚖️ *Weight Journey*",
            f"  Starting: {all_weights[0].weight_kg if all_weights else user.current_weight_kg}kg",
            f"  Current: {user.current_weight_kg}kg",
            f"  Goal: {user.goal_weight_kg}kg",
            f"  Lost: {lost_total:.1f}kg | Remaining: {remaining:.1f}kg\n",
        ]

        if user.current_weight_kg and user.goal_weight_kg and lost_total > 0:
            bar = progress_agent.build_progress_bar(
                user.current_weight_kg,
                all_weights[0].weight_kg if all_weights else user.current_weight_kg,
                user.goal_weight_kg,
            )
            lines.append(f"  {bar}\n")

        lines += [
            f"━━━━━━━━━━━━━━━━",
            f"📅 *Today*",
            f"  🔥 Calories: {today_cal:.0f} / {user.daily_calorie_target or 2000} kcal",
            f"  💧 Water: {today_water:.0f} / {user.daily_water_target_ml or 3000} ml\n",
            f"━━━━━━━━━━━━━━━━",
            f"🏋️ *This Week*",
            f"  Workouts: {completed_this_week} / {user.gym_days_per_week} completed",
            f"  Timeline: {user.timeline_months} months | Target: {user.weekly_weight_loss_target_kg or '?'}kg/week",
        ]

        await msg.edit_text(
            "\n".join(lines),
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

        # Fetch all week data
        weights = (await session.execute(
            select(WeightLog).where(WeightLog.user_id == user_id)
            .where(WeightLog.logged_at >= seven_days_ago)
        )).scalars().all()

        meals = (await session.execute(
            select(MealLog).where(MealLog.user_id == user_id)
            .where(MealLog.logged_at >= seven_days_ago)
        )).scalars().all()

        workouts = (await session.execute(
            select(WorkoutLog).where(WorkoutLog.user_id == user_id)
            .where(WorkoutLog.created_at >= seven_days_ago)
        )).scalars().all()

        waters = (await session.execute(
            select(WaterLog).where(WaterLog.user_id == user_id)
            .where(WaterLog.logged_at >= seven_days_ago)
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
