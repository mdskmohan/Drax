"""
Scheduled Celery tasks — run every 30 minutes and send to each user whose
configured notification time falls in the current 30-minute window.
All times are evaluated in the user's own timezone (user.timezone).
"""
import asyncio
import logging
import random
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta

from app.tasks.celery_app import celery_app
from app.config import settings

logger = logging.getLogger(__name__)


def _run(coro):
    """Run an async coroutine from a sync Celery task."""
    return asyncio.run(coro)


# ── Per-user scheduling helpers ────────────────────────────────────────────────

def _user_local_now(user) -> datetime:
    """Return the current datetime in the user's configured timezone."""
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(user.timezone or "Asia/Kolkata")
    except Exception:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo("UTC")
    return datetime.now(tz)


def _should_send(user, notif_type: str, now_local: datetime) -> bool:
    """
    Return True if this notification is due right now for this user.

    Logic:
    - Notification must be enabled
    - Today's name must be in the configured days (or always-on for water/report)
    - The configured time must fall within the current 30-minute window
    - It must not have been sent already today (in the user's local date)
    """
    pref = user.get_notification_pref(notif_type)

    if not pref.get("enabled", True):
        return False

    # Day-of-week check (not used for water_reminder — that uses hour range)
    if notif_type not in ("water_reminder",):
        today_name = now_local.strftime("%A")
        if notif_type == "weekly_report":
            if today_name != pref.get("day", "Sunday"):
                return False
        else:
            allowed_days = pref.get("days", list(_DAYS))
            if today_name not in allowed_days:
                return False

    # Time-window check
    configured_time = pref.get("time", "05:00")
    try:
        conf_h, conf_m = map(int, configured_time.split(":"))
    except (ValueError, AttributeError):
        return False

    conf_total = conf_h * 60 + conf_m
    now_total = now_local.hour * 60 + now_local.minute

    # 30-minute window: configured time <= now < configured time + 30
    if not (conf_total <= now_total < conf_total + 30):
        return False

    # Already-sent-today check
    last_sent_str = (user.notifications_last_sent or {}).get(notif_type)
    if last_sent_str:
        try:
            last_dt = datetime.fromisoformat(last_sent_str)
            if last_dt.tzinfo:
                last_dt = last_dt.astimezone(now_local.tzinfo)
            if last_dt.date() >= now_local.date():
                return False
        except Exception:
            pass

    return True


def _should_send_water(user, now_local: datetime) -> bool:
    """
    Return True if a water reminder is due right now.
    Water reminders are periodic (every N hours) within a configured hour range.
    """
    pref = user.get_notification_pref("water_reminder")

    if not pref.get("enabled", True):
        return False

    start_hour = pref.get("start_hour", 8)
    end_hour = pref.get("end_hour", 20)
    interval_hours = pref.get("interval_hours", 2)

    if not (start_hour <= now_local.hour <= end_hour):
        return False

    last_sent_str = (user.notifications_last_sent or {}).get("water_reminder")
    if last_sent_str:
        try:
            last_dt = datetime.fromisoformat(last_sent_str)
            if last_dt.tzinfo:
                last_dt = last_dt.astimezone(now_local.tzinfo)
            hours_since = (now_local - last_dt).total_seconds() / 3600
            if hours_since < interval_hours:
                return False
        except Exception:
            pass
    # If never sent before — only send if we're at least at start_hour
    elif now_local.hour < start_hour:
        return False

    return True


_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


async def _mark_sent(session, user, notif_type: str, now_local: datetime):
    """Persist the send timestamp so we don't double-send."""
    last_sent = dict(user.notifications_last_sent or {})
    last_sent[notif_type] = now_local.isoformat()
    user.notifications_last_sent = last_sent
    await session.commit()


# ── Morning plan ───────────────────────────────────────────────────────────────

@celery_app.task(name="app.tasks.scheduled.send_morning_plan")
def send_morning_plan():
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
            now_local = _user_local_now(user)
            if not _should_send(user, "morning_plan", now_local):
                continue
            try:
                today = now_local.strftime("%A, %B %d")
                day_of_week = now_local.strftime("%A")
                is_gym = _is_gym_day(user, now_local)
                water_target = user.daily_water_target_ml or 3000

                morning_msg = await motivation.get_morning_motivation(user)

                msg1 = (
                    f"🌅 *Good Morning, {user.first_name}! — {today}*\n\n"
                    f"{morning_msg}\n\n"
                    f"━━━━━━━━━━━━━━━━\n"
                    f"📋 *Today's Targets:*\n"
                    f"🔥 Calories: *{user.daily_calorie_target} kcal*\n"
                    f"💧 Water: *{water_target}ml*\n"
                    f"🏋️ Gym today: *{'YES — crush it! 💪' if is_gym else 'Rest / light activity'}*"
                )
                await bot.send_message(chat_id=user.id, text=msg1, parse_mode="Markdown")

                if is_gym:
                    workout_plan = await coach.generate_daily_workout(
                        user, day_of_week=day_of_week, is_gym_day=True
                    )
                    formatted = workout_plan.get("formatted_plan", "")
                    if not formatted:
                        from app.bot.handlers.workouts import _format_workout_plan
                        formatted = _format_workout_plan(workout_plan)

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
                        chat_id=user.id, text=formatted,
                        parse_mode="Markdown", reply_markup=keyboard,
                        disable_web_page_preview=True,
                    )
                else:
                    rest_msg = coach.generate_rest_day_message(user)
                    await bot.send_message(
                        chat_id=user.id,
                        text=f"😴 *Rest Day Plan:*\n\n{rest_msg}",
                        parse_mode="Markdown",
                    )

                meal_plan = await nutrition.generate_daily_meal_plan(user)
                meal_text = "🍽️ *Today's Meal Plan:*\n\n"
                meals = meal_plan.get("meals", {})
                meal_emojis = {"breakfast": "🌅", "lunch": "☀️", "dinner": "🌙", "snacks": "🍎"}
                for name, data in meals.items():
                    if isinstance(data, dict):
                        e = meal_emojis.get(name, "🍽️")
                        meal_text += (
                            f"{e} *{name.capitalize()}*\n"
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

                await _mark_sent(session, user, "morning_plan", now_local)
                logger.info(f"Morning plan sent to {user.id}")
            except Exception as e:
                logger.error(f"Morning plan failed for {user.id}: {e}")


# ── Pre-workout motivation ─────────────────────────────────────────────────────

@celery_app.task(name="app.tasks.scheduled.send_pre_workout_motivation")
def send_pre_workout_motivation():
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
            now_local = _user_local_now(user)
            if not _should_send(user, "preworkout", now_local):
                continue
            if not _is_gym_day(user, now_local):
                continue
            try:
                pump_msg = await motivation.get_pre_workout_pump(user, "strength")
                quote = motivation.get_daily_quote()
                text = (
                    f"🔥 *{user.first_name.upper()}, IT'S GYM TIME!*\n\n"
                    f"{pump_msg}\n\n"
                    f"💬 _{quote}_\n\n"
                    f"✅ Your workout plan was in your morning message — scroll up!\n"
                    f"Or type /workout to see it again. *See you at the gym!* 💪"
                )
                await bot.send_message(chat_id=user.id, text=text, parse_mode="Markdown")
                await _mark_sent(session, user, "preworkout", now_local)
                logger.info(f"Pre-workout motivation sent to {user.id}")
            except Exception as e:
                logger.error(f"Pre-workout failed for {user.id}: {e}")


# ── Evening check-in ──────────────────────────────────────────────────────────

@celery_app.task(name="app.tasks.scheduled.send_evening_checkin")
def send_evening_checkin():
    _run(_async_evening_checkin())


async def _async_evening_checkin():
    from telegram import Bot, InlineKeyboardMarkup, InlineKeyboardButton
    from sqlalchemy import select, func
    from app.database import AsyncSessionLocal
    from app.models.user import User, OnboardingState
    from app.models.meal_log import MealLog
    from app.models.water_log import WaterLog
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
            now_local = _user_local_now(user)
            if not _should_send(user, "evening_checkin", now_local):
                continue
            try:
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

                target_cal = user.daily_calorie_target or 2000
                target_water = user.daily_water_target_ml or 3000
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
                    chat_id=user.id, text=text,
                    parse_mode="Markdown", reply_markup=keyboard,
                )
                await _mark_sent(session, user, "evening_checkin", now_local)
                logger.info(f"Evening check-in sent to {user.id}")
            except Exception as e:
                logger.error(f"Evening check-in failed for {user.id}: {e}")


# ── Water reminder ─────────────────────────────────────────────────────────────

@celery_app.task(name="app.tasks.scheduled.send_water_reminder")
def send_water_reminder():
    _run(_async_water_reminder())


async def _async_water_reminder():
    from telegram import Bot
    from sqlalchemy import select, func
    from app.database import AsyncSessionLocal
    from app.models.user import User, OnboardingState
    from app.models.water_log import WaterLog

    bot = Bot(token=settings.telegram_bot_token)
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
            now_local = _user_local_now(user)
            if not _should_send_water(user, now_local):
                continue
            try:
                water_result = await session.execute(
                    select(func.sum(WaterLog.amount_ml))
                    .where(WaterLog.user_id == user.id)
                    .where(WaterLog.logged_at >= today_start)
                )
                today_water = water_result.scalar() or 0.0
                target = user.daily_water_target_ml or 3000

                if today_water < target * 0.5:
                    remaining = target - today_water
                    reminders = [
                        f"💧 Hey {user.first_name}! Don't forget to hydrate! {remaining:.0f}ml to go.",
                        f"🚰 Water check! You've had {today_water:.0f}ml. Drink up — {remaining:.0f}ml remaining!",
                        f"💦 Hydration reminder! {today_water:.0f}ml done. {remaining:.0f}ml more to hit your goal!",
                    ]
                    await bot.send_message(chat_id=user.id, text=random.choice(reminders))
                    await _mark_sent(session, user, "water_reminder", now_local)
            except Exception as e:
                logger.error(f"Water reminder failed for {user.id}: {e}")


# ── Weekly report ──────────────────────────────────────────────────────────────

@celery_app.task(name="app.tasks.scheduled.send_weekly_report")
def send_weekly_report():
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
    from app.agents.nutrition_agent import NutritionAgent

    bot = Bot(token=settings.telegram_bot_token)
    progress = ProgressAgent()
    nutrition = NutritionAgent()
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
            now_local = _user_local_now(user)
            if not _should_send(user, "weekly_report", now_local):
                continue
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

                # Auto-adjust calorie target based on actual weight change this week
                weight_logs = week_data["weight_logs"]
                if len(weight_logs) >= 2:
                    actual_change = weight_logs[-1]["weight_kg"] - weight_logs[0]["weight_kg"]
                    # Expected: ~0.5 kg/week loss (500 kcal deficit × 7 days / 7700 kcal/kg)
                    expected_change = -0.5
                    try:
                        new_target = await nutrition.adjust_calorie_target(
                            user, actual_change, expected_change
                        )
                        if new_target and abs(new_target - (user.daily_calorie_target or 0)) >= 50:
                            user.daily_calorie_target = new_target
                            user.calculate_macros()  # keep protein/carbs/fat in sync
                            await session.commit()
                            await bot.send_message(
                                chat_id=user.id,
                                text=(
                                    f"🔄 *Calorie target updated to {new_target} kcal/day*\n\n"
                                    f"Based on your weight change this week "
                                    f"({actual_change:+.1f} kg vs expected −0.5 kg), "
                                    f"I've adjusted your daily target to keep you on track."
                                ),
                                parse_mode="Markdown",
                            )
                    except Exception as e:
                        logger.warning(f"Calorie adjustment failed for {user.id}: {e}")

                # Rest-day suggestion: check if any scheduled gym day was skipped ≥2/3 weeks
                gym_schedule = user.gym_schedule or []
                if gym_schedule:
                    three_weeks_ago = datetime.now(timezone.utc) - timedelta(weeks=3)
                    skipped_logs = (await session.execute(
                        select(WorkoutLog)
                        .where(WorkoutLog.user_id == user.id)
                        .where(WorkoutLog.created_at >= three_weeks_ago)
                        .where(WorkoutLog.completion_notes == "Skipped")
                    )).scalars().all()

                    # Count skips per day of week
                    skip_days = Counter(
                        wl.scheduled_date.strftime("%A")
                        for wl in skipped_logs
                        if wl.scheduled_date
                    )
                    # Flag days in gym_schedule that were skipped 2+ times in 3 weeks
                    problem_days = [
                        day for day in gym_schedule
                        if skip_days.get(day, 0) >= 2
                    ]
                    if problem_days:
                        days_str = " and ".join(problem_days)
                        try:
                            await bot.send_message(
                                chat_id=user.id,
                                text=(
                                    f"📅 *Schedule Suggestion*\n\n"
                                    f"You've skipped *{days_str}* workouts multiple weeks in a row. "
                                    f"That's completely normal — life gets in the way.\n\n"
                                    f"Consider moving those to rest days and picking a day that works better for you. "
                                    f"Use /notifications to update your gym schedule."
                                ),
                                parse_mode="Markdown",
                            )
                        except Exception as e:
                            logger.warning(f"Rest-day suggestion failed for {user.id}: {e}")

                # Cuisine rotation suggestion: if same cuisine for ≥3 weeks, suggest trying a new one
                cuisine = getattr(user, "cuisine_preference", None)
                cuisine_changed_at = getattr(user, "cuisine_last_changed_at", None)
                if cuisine and cuisine_changed_at:
                    weeks_on_cuisine = (datetime.now(timezone.utc) - cuisine_changed_at).days / 7
                    if weeks_on_cuisine >= 3:
                        _OTHER_CUISINES = [
                            "Mediterranean", "Indian", "Japanese",
                            "Mexican", "Italian", "Chinese",
                        ]
                        alternatives = [c for c in _OTHER_CUISINES if c.lower() != cuisine.lower()]
                        suggestion = random.choice(alternatives)
                        try:
                            await bot.send_message(
                                chat_id=user.id,
                                text=(
                                    f"🍽️ *Variety suggestion*\n\n"
                                    f"You've been on *{cuisine.capitalize()} cuisine* for {int(weeks_on_cuisine)} weeks. "
                                    f"Want to mix it up? Try *{suggestion}* this week for fresh flavours and new nutrients.\n\n"
                                    f"Use /cuisine to switch anytime."
                                ),
                                parse_mode="Markdown",
                            )
                        except Exception as e:
                            logger.warning(f"Cuisine rotation suggestion failed for {user.id}: {e}")

                await _mark_sent(session, user, "weekly_report", now_local)
                logger.info(f"Weekly report sent to {user.id}")
            except Exception as e:
                logger.error(f"Weekly report failed for {user.id}: {e}")


# ── Gym-day helper ─────────────────────────────────────────────────────────────

def _is_gym_day(user, now_local: datetime | None = None) -> bool:
    """Check if today is a gym day using gym_schedule if set, else fall back to heuristic."""
    if now_local is None:
        now_local = _user_local_now(user)
    today_name = now_local.strftime("%A")

    if getattr(user, "gym_schedule", None):
        return today_name in user.gym_schedule

    day_index = now_local.weekday()  # 0=Mon, 6=Sun
    gym_days = user.gym_days_per_week or 3
    scheduled = list(range(0, min(gym_days, 6), max(1, 6 // gym_days)))
    return day_index in scheduled
