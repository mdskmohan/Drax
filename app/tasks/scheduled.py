"""
Scheduled Celery tasks for the daily bot loop.
All tasks are async-compatible through asyncio.run().
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta

from app.tasks.celery_app import celery_app
from app.config import settings

logger = logging.getLogger(__name__)


def _run(coro):
    """Run an async coroutine from a sync Celery task."""
    return asyncio.run(coro)


@celery_app.task(name="app.tasks.scheduled.send_morning_plan")
def send_morning_plan():
    """5:00 AM — Send morning plan + workout list to all active users (gym at 6:30-7 AM)."""
    _run(_async_send_morning_plan())


async def _async_send_morning_plan():
    from telegram import Bot, InlineKeyboardMarkup, InlineKeyboardButton
    from sqlalchemy import select
    from app.database import AsyncSessionLocal
    from app.models.user import User, OnboardingState
    from app.agents.motivation_agent import MotivationAgent
    from app.agents.nutrition_agent import NutritionAgent
    from app.agents.fitness_coach import FitnessCoachAgent

    bot = Bot(token=settings.telegram_bot_token)
    motivation = MotivationAgent()
    nutrition = NutritionAgent()
    coach = FitnessCoachAgent()

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(
                User.onboarding_state == OnboardingState.completed,
                User.is_active == True,
            )
        )
        users = result.scalars().all()

    for user in users:
        try:
            today = datetime.now().strftime("%A, %B %d")
            day_of_week = datetime.now().strftime("%A")
            is_gym = _is_gym_day(user)
            water_target = user.daily_water_target_ml or 3000

            # 1. Morning motivation (short)
            morning_msg = await motivation.get_morning_motivation(user)

            # ── Message 1: Motivation + daily targets ──────────────────────────
            msg1 = (
                f"🌅 *Good Morning, {user.first_name}! — {today}*\n\n"
                f"{morning_msg}\n\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"📋 *Today's Targets:*\n"
                f"🔥 Calories: *{user.daily_calorie_target} kcal*\n"
                f"💧 Water: *{water_target}ml*\n"
                f"🏋️ Gym today: *{'YES — crush it! 💪' if is_gym else 'Rest / light activity'}*\n"
                f"⏰ Gym time: *6:30 AM*"
            )
            await bot.send_message(chat_id=user.id, text=msg1, parse_mode="Markdown")

            # ── Message 2: Full Workout Plan (if gym day) ──────────────────────
            if is_gym:
                workout_plan = await coach.generate_daily_workout(
                    user, day_of_week=day_of_week, is_gym_day=True
                )
                formatted = workout_plan.get("formatted_plan", "")
                if not formatted:
                    from app.bot.handlers.workouts import _format_workout_plan
                    formatted = _format_workout_plan(workout_plan)

                # Add YouTube links if available
                yt_links = workout_plan.get("youtube_links", {})
                if yt_links:
                    formatted += "\n\n🎥 *Tutorial Videos:*\n"
                    for ex, url in list(yt_links.items())[:4]:
                        formatted += f"• [{ex}]({url})\n"

                formatted += (
                    f"\n\n⏱️ Duration: {workout_plan.get('duration_minutes', 45)} min  "
                    f"|  🔥 ~{workout_plan.get('calories_burned_estimate', 300)} kcal burned"
                    f"\n\n_Reply ✅ done / ❌ skip after your session_"
                )

                if len(formatted) > 4000:
                    formatted = formatted[:4000] + "..."

                keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("✅ Completed!", callback_data="workout_done"),
                        InlineKeyboardButton("⚡ Partial", callback_data="workout_partial"),
                    ],
                    [
                        InlineKeyboardButton("😴 Skipped", callback_data="workout_skipped"),
                        InlineKeyboardButton("🤕 Pain/Injury", callback_data="workout_pain"),
                    ],
                ])

                await bot.send_message(
                    chat_id=user.id,
                    text=formatted,
                    parse_mode="Markdown",
                    reply_markup=keyboard,
                    disable_web_page_preview=True,
                )
            else:
                # Rest day — send light activity suggestion
                rest_msg = await coach.generate_rest_day_message(user)
                await bot.send_message(chat_id=user.id, text=f"😴 *Rest Day Plan:*\n\n{rest_msg}", parse_mode="Markdown")

            # ── Message 3: Meal plan ───────────────────────────────────────────
            meal_plan = await nutrition.generate_daily_meal_plan(user)
            meal_text = f"🍽️ *Today's Meal Plan:*\n\n"
            meals = meal_plan.get("meals", {})
            meal_emojis = {"breakfast": "🌅", "lunch": "☀️", "dinner": "🌙", "snacks": "🍎"}
            for name, data in meals.items():
                if isinstance(data, dict):
                    emoji = meal_emojis.get(name, "🍽️")
                    meal_text += (
                        f"{emoji} *{name.capitalize()}*\n"
                        f"   {data.get('description', '')[:70]}\n"
                        f"   🔥 {data.get('calories', 0):.0f} kcal | 💪 {data.get('protein_g', 0):.0f}g protein\n\n"
                    )
            tip = meal_plan.get("nutrition_tip", "")
            if tip:
                meal_text += f"💡 *Tip:* _{tip}_\n\n"
            meal_text += "_Log meals with /meal — I'll track your calories all day!_"

            if len(meal_text) > 4000:
                meal_text = meal_text[:4000]

            await bot.send_message(chat_id=user.id, text=meal_text, parse_mode="Markdown")

            logger.info(f"5 AM morning pack sent to user {user.id} (gym={is_gym})")
        except Exception as e:
            logger.error(f"Failed to send morning plan to {user.id}: {e}")


@celery_app.task(name="app.tasks.scheduled.send_pre_workout_motivation")
def send_pre_workout_motivation():
    """6:00 AM — Final pump-up 30 minutes before gym (gym at 6:30-7 AM)."""
    _run(_async_pre_workout_motivation())


async def _async_pre_workout_motivation():
    from telegram import Bot
    from sqlalchemy import select
    from app.database import AsyncSessionLocal
    from app.models.user import User, OnboardingState
    from app.agents.motivation_agent import MotivationAgent

    bot = Bot(token=settings.telegram_bot_token)
    motivation = MotivationAgent()

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(
                User.onboarding_state == OnboardingState.completed,
                User.is_active == True,
            )
        )
        users = result.scalars().all()

    for user in users:
        if not _is_gym_day(user):
            continue
        try:
            pump_msg = await motivation.get_pre_workout_pump(user, "strength")
            quote = motivation.get_daily_quote()

            text = (
                f"🔥 *30 MINUTES TO GYM, {user.first_name.upper()}!*\n\n"
                f"{pump_msg}\n\n"
                f"💬 _{quote}_\n\n"
                f"✅ Your workout plan was sent at 5 AM — scroll up!\n"
                f"Or type /workout to see it again. *See you at the gym!* 💪"
            )
            await bot.send_message(chat_id=user.id, text=text, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Failed to send pre-workout to {user.id}: {e}")


@celery_app.task(name="app.tasks.scheduled.send_evening_checkin")
def send_evening_checkin():
    """9:00 PM — Ask if workout was completed, check calories/water."""
    _run(_async_evening_checkin())


async def _async_evening_checkin():
    from telegram import Bot, InlineKeyboardMarkup, InlineKeyboardButton
    from sqlalchemy import select, func
    from app.database import AsyncSessionLocal
    from app.models.user import User, OnboardingState
    from app.models.meal_log import MealLog
    from app.models.water_log import WaterLog
    from app.models.workout_log import WorkoutLog
    from app.agents.hydration_agent import HydrationAgent

    bot = Bot(token=settings.telegram_bot_token)
    hydration = HydrationAgent()
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(
                User.onboarding_state == OnboardingState.completed,
                User.is_active == True,
            )
        )
        users = result.scalars().all()

        for user in users:
            try:
                # Get today's stats
                cal_result = await session.execute(
                    select(func.sum(MealLog.calories))
                    .where(MealLog.user_id == user.id)
                    .where(MealLog.logged_at >= today_start)
                )
                today_cal = cal_result.scalar() or 0.0

                water_result = await session.execute(
                    select(func.sum(WaterLog.amount_ml))
                    .where(WaterLog.user_id == user.id)
                    .where(WaterLog.logged_at >= today_start)
                )
                today_water = water_result.scalar() or 0.0

                # Check workout completion
                workout_result = await session.execute(
                    select(WorkoutLog)
                    .where(WorkoutLog.user_id == user.id)
                    .where(WorkoutLog.scheduled_date >= today_start)
                )
                today_workout = workout_result.scalar_one_or_none()

                target_cal = user.daily_calorie_target or 2000
                target_water = user.daily_water_target_ml or 3000
                water_status = hydration.get_hydration_status(int(today_water), target_water)

                cal_status = "✅" if today_cal <= target_cal else "⚠️"
                water_icon = "✅" if today_water >= target_water * 0.8 else "⚠️"

                text = (
                    f"🌙 *Evening Check-In, {user.first_name}!*\n\n"
                    f"📊 *Today's Summary:*\n"
                    f"{cal_status} Calories: {today_cal:.0f} / {target_cal} kcal\n"
                    f"{water_icon} Water: {today_water:.0f} / {target_water} ml\n\n"
                )

                if today_water < target_water * 0.8:
                    remaining_water = target_water - today_water
                    text += f"💧 *Drink {remaining_water:.0f}ml more water before bed!*\n\n"

                text += "Did you complete your workout today? 🏋️"

                keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("✅ Done!", callback_data="workout_done"),
                        InlineKeyboardButton("😴 Skipped", callback_data="workout_skipped"),
                    ],
                    [InlineKeyboardButton("🤕 Pain/Injury", callback_data="workout_pain")],
                ])

                await bot.send_message(
                    chat_id=user.id,
                    text=text,
                    parse_mode="Markdown",
                    reply_markup=keyboard,
                )
            except Exception as e:
                logger.error(f"Failed evening check-in for {user.id}: {e}")


@celery_app.task(name="app.tasks.scheduled.send_water_reminder")
def send_water_reminder():
    """Every 2 hours — nudge users who haven't hit 50% of water goal."""
    _run(_async_water_reminder())


async def _async_water_reminder():
    from telegram import Bot
    from sqlalchemy import select, func
    from app.database import AsyncSessionLocal
    from app.models.user import User, OnboardingState
    from app.models.water_log import WaterLog

    bot = Bot(token=settings.telegram_bot_token)
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    current_hour = datetime.now().hour

    # Only send during waking hours (8 AM - 8 PM local)
    if not (8 <= current_hour <= 20):
        return

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(
                User.onboarding_state == OnboardingState.completed,
                User.is_active == True,
            )
        )
        users = result.scalars().all()

        for user in users:
            try:
                water_result = await session.execute(
                    select(func.sum(WaterLog.amount_ml))
                    .where(WaterLog.user_id == user.id)
                    .where(WaterLog.logged_at >= today_start)
                )
                today_water = water_result.scalar() or 0.0
                target = user.daily_water_target_ml or 3000

                # Only remind if below 50% of target
                if today_water < target * 0.5:
                    remaining = target - today_water
                    reminders = [
                        f"💧 Hey {user.first_name}! Don't forget to hydrate! {remaining:.0f}ml to go.",
                        f"🚰 Water check! You've had {today_water:.0f}ml. Drink up — {remaining:.0f}ml remaining!",
                        f"💦 Hydration reminder! {today_water:.0f}ml done. {remaining:.0f}ml more to hit your goal!",
                    ]
                    import random
                    await bot.send_message(
                        chat_id=user.id,
                        text=random.choice(reminders),
                    )
            except Exception as e:
                logger.error(f"Water reminder failed for {user.id}: {e}")


@celery_app.task(name="app.tasks.scheduled.send_weekly_report")
def send_weekly_report():
    """Sunday 8 AM — Send weekly progress report."""
    _run(_async_weekly_report())


async def _async_weekly_report():
    from telegram import Bot
    from sqlalchemy import select
    from app.database import AsyncSessionLocal
    from app.models.user import User, OnboardingState
    from app.models.weight_log import WeightLog
    from app.models.meal_log import MealLog
    from app.models.water_log import WaterLog
    from app.models.workout_log import WorkoutLog
    from app.agents.progress_agent import ProgressAgent

    bot = Bot(token=settings.telegram_bot_token)
    progress = ProgressAgent()
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(
                User.onboarding_state == OnboardingState.completed,
                User.is_active == True,
            )
        )
        users = result.scalars().all()

        for user in users:
            try:
                weights = (await session.execute(
                    select(WeightLog).where(WeightLog.user_id == user.id)
                    .where(WeightLog.logged_at >= seven_days_ago)
                )).scalars().all()

                meals = (await session.execute(
                    select(MealLog).where(MealLog.user_id == user.id)
                    .where(MealLog.logged_at >= seven_days_ago)
                )).scalars().all()

                workouts = (await session.execute(
                    select(WorkoutLog).where(WorkoutLog.user_id == user.id)
                    .where(WorkoutLog.created_at >= seven_days_ago)
                )).scalars().all()

                waters = (await session.execute(
                    select(WaterLog).where(WaterLog.user_id == user.id)
                    .where(WaterLog.logged_at >= seven_days_ago)
                )).scalars().all()

                week_data = {
                    "weight_logs": [{"weight_kg": w.weight_kg, "logged_at": str(w.logged_at)} for w in weights],
                    "meal_logs": [{"calories": m.calories, "protein_g": m.protein_g} for m in meals],
                    "workout_logs": [{"completed": w.completed} for w in workouts],
                    "water_logs": [{"amount_ml": w.amount_ml} for w in waters],
                }

                report = await progress.generate_weekly_report(user, week_data)

                if len(report) > 4000:
                    report = report[:4000] + "..."

                await bot.send_message(
                    chat_id=user.id,
                    text=f"📊 *Weekly Report*\n\n{report}",
                    parse_mode="Markdown",
                )
                logger.info(f"Weekly report sent to {user.id}")
            except Exception as e:
                logger.error(f"Weekly report failed for {user.id}: {e}")


def _is_gym_day(user) -> bool:
    """Simple heuristic — is today a gym day based on user's gym_days_per_week?"""
    day = datetime.now().weekday()  # 0=Mon, 6=Sun
    gym_days = user.gym_days_per_week or 3
    # Distribute gym days evenly across the week
    scheduled = list(range(0, min(gym_days, 6), max(1, 6 // gym_days)))
    return day in scheduled
