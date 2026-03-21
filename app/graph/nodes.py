"""
Graph Nodes — each node wraps an existing agent and returns a state update.
Nodes are plain async functions: (DraxState) -> dict

The graph flows:
  START → load_user → supervisor → [agent node] → [optional chain] → END
"""
from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import select, func

from app.graph.state import DraxState
from app.database import AsyncSessionLocal
from app.models.user import User, OnboardingState
from app.models.meal_log import MealLog
from app.models.water_log import WaterLog
from app.agents.fitness_coach import FitnessCoachAgent
from app.agents.nutrition_agent import NutritionAgent
from app.agents.hydration_agent import HydrationAgent
from app.agents.motivation_agent import MotivationAgent
from app.agents.progress_agent import ProgressAgent
from app.agents.recovery_agent import RecoveryAgent

# ── Agent singletons (shared across all graph invocations) ────────────────────
_coach = FitnessCoachAgent()
_nutrition = NutritionAgent()
_hydration = HydrationAgent()
_motivation = MotivationAgent()
_progress = ProgressAgent()
_recovery = RecoveryAgent()


# ── Helper ────────────────────────────────────────────────────────────────────

def _today_start():
    return datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)


# ── Node: Load user ───────────────────────────────────────────────────────────

async def load_user_node(state: DraxState) -> dict:
    """
    Loads the User object from DB. Runs before the supervisor so every
    downstream node has access to the full user profile.
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.id == state["user_id"])
        )
        user = result.scalar_one_or_none()
    return {"user": user}


# ── Node: Meal logging ────────────────────────────────────────────────────────

async def log_meal_node(state: DraxState) -> dict:
    """Parse meal text → get nutrition → save to DB → return feedback."""
    user = state["user"]
    food_text = state.get("user_input", "")
    context = state.get("context", {})
    meal_type = context.get("meal_type", "snack")

    # Parse nutrition
    nutrition = await _nutrition.parse_meal(user, food_text)
    nutrition["meal_type"] = meal_type

    # Get today's running total
    async with AsyncSessionLocal() as session:
        cal_result = await session.execute(
            select(func.sum(MealLog.calories))
            .where(MealLog.user_id == user.id)
            .where(MealLog.logged_at >= _today_start())
        )
        today_cal = cal_result.scalar() or 0.0

        # Save to DB
        log = MealLog(
            user_id=user.id,
            meal_type=meal_type,
            food_description=food_text,
            parsed_foods=nutrition.get("foods", []),
            calories=nutrition.get("total_calories", 0),
            protein_g=nutrition.get("total_protein_g", 0),
            carbs_g=nutrition.get("total_carbs_g", 0),
            fat_g=nutrition.get("total_fat_g", 0),
            fiber_g=nutrition.get("total_fiber_g", 0),
            sodium_mg=nutrition.get("total_sodium_mg", 0),
            source="text",
        )
        session.add(log)
        await session.commit()

    new_total = today_cal + nutrition.get("total_calories", 0)
    feedback = await _nutrition.get_meal_feedback(user, food_text, nutrition, new_total)

    remaining = (user.daily_calorie_target or 2000) - new_total
    cal = nutrition.get("total_calories", 0)

    response = (
        f"✅ *{meal_type.capitalize()} logged!*\n\n"
        f"🔥 Calories: *{cal:.0f} kcal*\n"
        f"💪 Protein: {nutrition.get('total_protein_g',0):.1f}g  "
        f"🌾 Carbs: {nutrition.get('total_carbs_g',0):.1f}g  "
        f"🧈 Fat: {nutrition.get('total_fat_g',0):.1f}g\n\n"
        f"📈 Today: {new_total:.0f} / {user.daily_calorie_target or 2000} kcal  "
        f"({'✅' if remaining >= 0 else '⚠️'} {abs(remaining):.0f} kcal {'left' if remaining >= 0 else 'over'})\n\n"
        f"💬 _{feedback}_"
    )

    # Chain: if water is low after eating, nudge hydration
    chain_to = await _should_nudge_water(user)

    return {
        "nutrition_data": nutrition,
        "response": response,
        "chain_to": chain_to,
    }


# ── Node: Water logging ───────────────────────────────────────────────────────

async def log_water_node(state: DraxState) -> dict:
    """Parse water amount → save → return hydration status."""
    user = state["user"]
    text = state.get("user_input", "")

    amount_ml = _hydration.parse_water_amount(text)
    if not amount_ml:
        return {"response": "❌ Couldn't parse that amount. Try: _500ml_, _2 glasses_, _1 bottle_"}

    async with AsyncSessionLocal() as session:
        session.add(WaterLog(user_id=user.id, amount_ml=amount_ml))
        await session.flush()

        total_result = await session.execute(
            select(func.sum(WaterLog.amount_ml))
            .where(WaterLog.user_id == user.id)
            .where(WaterLog.logged_at >= _today_start())
        )
        today_total = total_result.scalar() or 0.0
        await session.commit()

    target = user.daily_water_target_ml or 3000
    status = _hydration.get_hydration_status(int(today_total), target)
    bar = _hydration.format_progress_bar(int(today_total), target)

    response = (
        f"💧 *+{amount_ml}ml logged!*\n\n"
        f"Today: *{today_total:.0f}ml* / *{target}ml*\n"
        f"{bar}\n\n"
        f"{status['emoji']} {status['message']}"
    )

    return {"water_status": status, "response": response, "chain_to": ""}


# ── Node: Workout generation ──────────────────────────────────────────────────

async def get_workout_node(state: DraxState) -> dict:
    """Generate today's workout plan, with progressive overload from exercise history."""
    from datetime import timedelta
    from app.models.exercise_log import ExerciseLog

    user = state["user"]
    day = datetime.now().strftime("%A")

    # Fetch last 4 weeks of exercise logs for progressive overload
    four_weeks_ago = datetime.now(timezone.utc) - timedelta(weeks=4)
    async with AsyncSessionLocal() as session:
        logs_result = await session.execute(
            select(ExerciseLog)
            .where(ExerciseLog.user_id == user.id)
            .where(ExerciseLog.logged_at >= four_weeks_ago)
            .order_by(ExerciseLog.logged_at.desc())
        )
        exercise_history = [
            {
                "exercise_name": log.exercise_name,
                "weight_kg": log.weight_kg,
                "reps": log.reps,
                "sets": log.sets,
                "logged_at": str(log.logged_at),
            }
            for log in logs_result.scalars().all()
        ]

    # Fetch full coaching context (yesterday's diet + workout history)
    coaching_ctx = await fetch_coaching_context(user.id)

    plan = await _coach.generate_daily_workout(
        user, day_of_week=day, is_gym_day=True,
        exercise_history=exercise_history or None,
        yesterday_nutrition=coaching_ctx["yesterday_nutrition"],
        recent_workout_history=coaching_ctx["recent_workout_history"],
    )

    # Format
    formatted = plan.get("formatted_plan") or _format_plan(plan)
    yt = plan.get("youtube_links", {})
    if yt:
        formatted += "\n\n🎥 *Tutorials:*\n" + "".join(
            f"• [{ex}]({url})\n" for ex, url in list(yt.items())[:3]
        )
    formatted += (
        f"\n\n⏱️ {plan.get('duration_minutes', 45)} min  "
        f"🔥 ~{plan.get('calories_burned_estimate', 300)} kcal"
    )

    # Chain to motivation after showing workout
    motivation = await _motivation.get_pre_workout_pump(user, plan.get("workout_type", "strength"))
    formatted = f"💪 _{motivation}_\n\n━━━━━━━━━━━━━━━━\n\n" + formatted

    return {
        "workout_plan": plan,
        "response": formatted,
        "chain_to": "",
        "response_data": {"show_workout_buttons": True},
    }


# ── Node: Weight logging ──────────────────────────────────────────────────────

async def log_weight_node(state: DraxState) -> dict:
    """Parse and save weight, return AI feedback."""
    from app.models.weight_log import WeightLog

    user = state["user"]
    text = state.get("user_input", "")

    try:
        weight = float(text.replace("kg", "").strip().split()[0])
        assert 30 <= weight <= 300
    except Exception:
        return {"response": "Please send your weight as a number in kg (e.g., _89.5_)"}

    feedback = await _progress.log_weight_feedback(user, weight)

    async with AsyncSessionLocal() as session:
        session.add(WeightLog(user_id=user.id, weight_kg=weight, ai_feedback=feedback))
        # Update current weight on user profile
        result = await session.execute(select(User).where(User.id == user.id))
        db_user = result.scalar_one()
        old_weight = db_user.current_weight_kg
        db_user.current_weight_kg = weight
        # Fetch earliest weight log for correct all-time progress bar start
        first_log_r = await session.execute(
            select(WeightLog)
            .where(WeightLog.user_id == user.id)
            .order_by(WeightLog.logged_at)
            .limit(1)
        )
        first_log = first_log_r.scalar_one_or_none()
        start_weight = first_log.weight_kg if first_log else old_weight
        await session.commit()

    change = (old_weight - weight) if old_weight else 0
    bar = ""
    if user.goal_weight_kg and start_weight:
        bar = "\n" + _progress.build_progress_bar(weight, start_weight, user.goal_weight_kg) + "\n"

    response = (
        f"⚖️ *Weight logged: {weight}kg*\n"
        f"{'📉' if change > 0 else '📈' if change < 0 else '➡️'} "
        f"{'−' if change > 0 else '+'}{abs(round(change,2))}kg from last log\n"
        f"{bar}\n💬 _{feedback}_"
    )

    return {"response": response, "chain_to": ""}


# ── Node: Progress ────────────────────────────────────────────────────────────

async def get_progress_node(state: DraxState) -> dict:
    """Return quick progress summary."""
    from datetime import timedelta
    from app.models.weight_log import WeightLog
    from app.models.workout_log import WorkoutLog

    user = state["user"]
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)

    async with AsyncSessionLocal() as session:
        # Today's calories
        cal_r = await session.execute(
            select(func.sum(MealLog.calories))
            .where(MealLog.user_id == user.id)
            .where(MealLog.logged_at >= _today_start())
        )
        today_cal = cal_r.scalar() or 0.0

        # Today's water
        water_r = await session.execute(
            select(func.sum(WaterLog.amount_ml))
            .where(WaterLog.user_id == user.id)
            .where(WaterLog.logged_at >= _today_start())
        )
        today_water = water_r.scalar() or 0.0

        # Weekly workouts
        wk_r = await session.execute(
            select(WorkoutLog)
            .where(WorkoutLog.user_id == user.id)
            .where(WorkoutLog.created_at >= seven_days_ago)
        )
        weekly_wk = wk_r.scalars().all()
        completed_wk = sum(1 for w in weekly_wk if w.completed)

        # Weight logs (all time for progress bar)
        wl_r = await session.execute(
            select(WeightLog).where(WeightLog.user_id == user.id).order_by(WeightLog.logged_at)
        )
        all_weights = wl_r.scalars().all()

    lost_total = (all_weights[0].weight_kg - user.current_weight_kg) if all_weights else 0
    remaining = (user.current_weight_kg or 0) - (user.goal_weight_kg or 0)

    bar = ""
    if all_weights and user.goal_weight_kg:
        bar = "\n" + _progress.build_progress_bar(
            user.current_weight_kg, all_weights[0].weight_kg, user.goal_weight_kg
        ) + "\n"

    response = (
        f"📊 *Progress Dashboard*\n\n"
        f"⚖️ {user.current_weight_kg}kg → Goal: {user.goal_weight_kg}kg\n"
        f"📉 Lost: {round(lost_total,1)}kg | Remaining: {round(remaining,1)}kg\n"
        f"{bar}\n"
        f"━━━━━━━━━━━━\n"
        f"🔥 Today calories: {today_cal:.0f} / {user.daily_calorie_target or 2000} kcal\n"
        f"💧 Today water: {today_water:.0f} / {user.daily_water_target_ml or 3000} ml\n"
        f"🏋️ This week: {completed_wk} / {user.gym_days_per_week} workouts done"
    )

    return {"response": response, "chain_to": ""}


# ── Node: Motivation ──────────────────────────────────────────────────────────

async def get_motivation_node(state: DraxState) -> dict:
    user = state["user"]
    msg = await _motivation.get_morning_motivation(user)
    video = await _motivation.get_motivation_video()
    response = f"💪 *Daily Motivation*\n\n{msg}"
    if video:
        response += f"\n\n🎥 [{video['title']}]({video['url']})"
    return {"response": response, "chain_to": ""}


# ── Node: Full daily plan ─────────────────────────────────────────────────────

async def get_plan_node(state: DraxState) -> dict:
    """Generate full day plan: meal plan + workout plan."""
    from datetime import timedelta
    from app.models.exercise_log import ExerciseLog

    user = state["user"]
    day = datetime.now().strftime("%A, %B %d")
    week_day = datetime.now().strftime("%A")

    four_weeks_ago = datetime.now(timezone.utc) - timedelta(weeks=4)
    async with AsyncSessionLocal() as session:
        logs_result = await session.execute(
            select(ExerciseLog)
            .where(ExerciseLog.user_id == user.id)
            .where(ExerciseLog.logged_at >= four_weeks_ago)
            .order_by(ExerciseLog.logged_at.desc())
        )
        exercise_history = [
            {"exercise_name": l.exercise_name, "weight_kg": l.weight_kg,
             "reps": l.reps, "sets": l.sets, "logged_at": str(l.logged_at)}
            for l in logs_result.scalars().all()
        ] or None

    coaching_ctx = await fetch_coaching_context(user.id)

    workout_plan = await _coach.generate_daily_workout(
        user, day_of_week=week_day, exercise_history=exercise_history,
        yesterday_nutrition=coaching_ctx["yesterday_nutrition"],
        recent_workout_history=coaching_ctx["recent_workout_history"],
    )
    today_workout_ctx = {
        "is_gym_day": True,
        "workout_type": workout_plan.get("workout_type", "strength"),
        "calories_burned": workout_plan.get("calories_burned_estimate", 300),
    }
    meal_plan = await _nutrition.generate_daily_meal_plan(
        user,
        today_workout=today_workout_ctx,
        yesterday_intake=coaching_ctx["yesterday_nutrition"],
    )

    response = (
        f"📋 *Daily Plan — {day}*\n\n"
        f"🔥 Calories: *{user.daily_calorie_target} kcal*  💧 Water: *{user.daily_water_target_ml}ml*\n\n"
        f"━━━━━━━━━━━━━━━━\n🍽️ *MEALS*\n\n"
    )

    emojis = {"breakfast": "🌅", "lunch": "☀️", "dinner": "🌙", "snacks": "🍎"}
    for name, data in (meal_plan.get("meals") or {}).items():
        if isinstance(data, dict):
            response += (
                f"{emojis.get(name,'🍽️')} *{name.capitalize()}*: "
                f"{data.get('description','')[:60]} "
                f"({data.get('calories',0):.0f} kcal)\n"
            )

    response += f"\n━━━━━━━━━━━━━━━━\n🏋️ *WORKOUT*\n\n"
    formatted_wk = workout_plan.get("formatted_plan") or _format_plan(workout_plan)
    response += formatted_wk[:1200]

    return {
        "nutrition_data": meal_plan,
        "workout_plan": workout_plan,
        "response": response,
        "chain_to": "",
    }


# ── Node: Pain / Recovery ─────────────────────────────────────────────────────

async def report_pain_node(state: DraxState) -> dict:
    user = state["user"]
    pain_text = state.get("user_input", "")

    assessment = await _recovery.assess_pain(user, pain_text)
    modified = await _recovery.generate_modified_workout(user, assessment)

    severity = assessment.get("severity", "mild")
    see_doc = assessment.get("see_doctor", False)
    recommendation = assessment.get("recommendation", "")

    response = (
        f"🩺 *Pain Assessment: {severity.upper()}*\n\n"
        f"⚠️ {recommendation}\n\n"
    )
    if see_doc:
        response += "🏥 *Please see a doctor before training.*\n\n"
    response += f"💪 *Modified Workout:*\n\n{modified}"

    return {"pain_assessment": assessment, "response": response, "chain_to": ""}


# ── Node: General fallback ────────────────────────────────────────────────────

async def general_node(state: DraxState) -> dict:
    import asyncio
    from app.services.llm import llm
    user = state["user"]
    user_input = state.get("user_input", "")

    # Build a profile-aware system prompt so coaching answers are personalised
    if user:
        level = user.workout_level.value if user.workout_level else "beginner"
        gym_days = user.gym_days_per_week or 3
        current_w = user.current_weight_kg or "?"
        goal_w = user.goal_weight_kg or "?"
        profile = (
            f"User profile: {user.first_name}, {current_w}kg → {goal_w}kg goal, "
            f"{level} level, {gym_days} gym days/week."
        )
    else:
        profile = ""

    system = (
        f"You are Drax, an expert AI personal fitness coach. {profile} "
        f"Answer fitness and coaching questions with specific, evidence-based advice "
        f"tailored to the user's profile above. When asked about workout splits, scheduling, "
        f"or methodology (push/pull/legs, bro split, etc.), explain the options clearly and "
        f"give a concrete recommendation based on their available days and level. "
        f"Use markdown formatting. Be thorough but conversational — this is a Telegram chat."
    )

    response = await llm.chat(
        messages=[{"role": "user", "content": user_input}],
        system=system,
        max_tokens=800,
    )

    # Fire-and-forget: extract any persistent preferences from this message
    # so Drax remembers them in every future session without blocking the reply.
    if user:
        asyncio.create_task(_extract_and_store_preferences(user.id, user_input))

    return {"response": response, "chain_to": ""}


async def _extract_and_store_preferences(user_id: int, user_input: str) -> None:
    """
    Run a fast LLM call to detect any persistent fitness preferences, dislikes,
    or self-reported physical constraints in the message. Store them in
    user.chat_memory so they are injected into every future LLM call.
    """
    from app.services.llm import llm
    from app.models.user import User

    try:
        result = await llm.json(
            messages=[{"role": "user", "content": user_input}],
            system=(
                "Extract ONLY persistent, actionable fitness or nutrition preferences "
                "worth remembering long-term from this message.\n"
                "Extract: dislikes (exercises, foods), preferences (timing, style), "
                "self-reported physical limitations (weak joints, old injuries).\n"
                "Do NOT extract: questions, temporary states, generic statements, "
                "or things already standard in a profile (name, weight, etc.).\n"
                "Examples worth extracting:\n"
                '  "I hate burpees" → {"key": "dislikes_burpees", "value": "hates burpees"}\n'
                '  "my left shoulder is dodgy" → {"key": "weak_left_shoulder", "value": "reports weak/injured left shoulder"}\n'
                '  "I prefer training at night" → {"key": "training_timing", "value": "prefers evening training"}\n'
                'Return JSON: {"preferences": [{"key": "snake_case_key", "value": "..."}]}\n'
                'Return {"preferences": []} if nothing worth storing.'
            ),
            fast=True,
            max_tokens=150,
        )
        prefs = result.get("preferences", [])
        if not prefs:
            return

        async with AsyncSessionLocal() as session:
            q = await session.execute(select(User).where(User.id == user_id))
            user = q.scalar_one_or_none()
            if not user:
                return

            memory = list(user.chat_memory or [])
            existing = {m["key"]: i for i, m in enumerate(memory)}
            now = datetime.now(timezone.utc).isoformat()

            for pref in prefs:
                key = (pref.get("key") or "").strip()
                value = (pref.get("value") or "").strip()
                if not key or not value:
                    continue
                if key in existing:
                    memory[existing[key]]["value"] = value
                    memory[existing[key]]["noted_at"] = now
                else:
                    memory.append({"key": key, "value": value, "noted_at": now})
                    existing[key] = len(memory) - 1

            user.chat_memory = memory[-25:]   # cap at 25 entries
            await session.commit()
    except Exception:
        pass  # never let this crash the main response flow


# ── Node: Chain router ────────────────────────────────────────────────────────

async def chain_check_node(state: DraxState) -> dict:
    """
    After the primary agent runs, check if we should chain to another action.
    E.g., after meal log → nudge water if low.
    This node just passes through; the conditional edge does the routing.
    """
    return {}


def route_chain(state: DraxState) -> str:
    """Conditional edge: go to chain_to node, or END."""
    chain_to = state.get("chain_to", "")
    if chain_to:
        return chain_to
    return "__end__"


# ── Node: Water nudge (chained after meal log) ────────────────────────────────

async def water_nudge_node(state: DraxState) -> dict:
    """Appends a water reminder to the existing response."""
    user = state["user"]
    existing = state.get("response", "")
    target = user.daily_water_target_ml or 3000

    async with AsyncSessionLocal() as session:
        total_r = await session.execute(
            select(func.sum(WaterLog.amount_ml))
            .where(WaterLog.user_id == user.id)
            .where(WaterLog.logged_at >= _today_start())
        )
        today_water = total_r.scalar() or 0.0

    status = _hydration.get_hydration_status(int(today_water), target)
    bar = _hydration.format_progress_bar(int(today_water), target)

    nudge = (
        f"\n\n━━━━━━━━━━━━\n"
        f"💧 *Water check:* {today_water:.0f}ml / {target}ml\n"
        f"{bar}\n"
        f"{status['emoji']} {status['message']}"
    )

    return {"response": existing + nudge, "chain_to": ""}


# ── Coaching context helper ───────────────────────────────────────────────────

async def fetch_coaching_context(user_id: int) -> dict:
    """
    Fetch all the live data a personal trainer + nutritionist needs:
    - Yesterday's actual nutrition (calories, protein, carbs, fat, water)
    - Last 7 days of workout history (type, completion status, muscle groups, pain)

    Returns dict with keys: yesterday_nutrition, recent_workout_history
    """
    from datetime import timedelta
    from app.models.workout_log import WorkoutLog

    now_utc = datetime.now(timezone.utc)
    yesterday_start = (now_utc - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_end = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    seven_days_ago = now_utc - timedelta(days=7)

    async with AsyncSessionLocal() as session:
        macro_r = await session.execute(
            select(
                func.sum(MealLog.calories),
                func.sum(MealLog.protein_g),
                func.sum(MealLog.carbs_g),
                func.sum(MealLog.fat_g),
            )
            .where(MealLog.user_id == user_id)
            .where(MealLog.logged_at >= yesterday_start)
            .where(MealLog.logged_at < yesterday_end)
        )
        macro_row = macro_r.one()

        water_r = await session.execute(
            select(func.sum(WaterLog.amount_ml))
            .where(WaterLog.user_id == user_id)
            .where(WaterLog.logged_at >= yesterday_start)
            .where(WaterLog.logged_at < yesterday_end)
        )
        yesterday_water = water_r.scalar() or 0.0

        wl_r = await session.execute(
            select(WorkoutLog)
            .where(WorkoutLog.user_id == user_id)
            .where(WorkoutLog.created_at >= seven_days_ago)
            .order_by(WorkoutLog.created_at.desc())
        )
        workout_rows = wl_r.scalars().all()

    yesterday_nutrition = {
        "calories": round(macro_row[0] or 0),
        "protein_g": round(macro_row[1] or 0, 1),
        "carbs_g": round(macro_row[2] or 0, 1),
        "fat_g": round(macro_row[3] or 0, 1),
        "water_ml": round(yesterday_water),
    }

    recent_workout_history = []
    for wl in workout_rows:
        muscle_groups = list({
            ex.get("muscle_group", "").lower()
            for ex in (wl.exercises or [])
            if ex.get("muscle_group")
        })
        recent_workout_history.append({
            "date": str(wl.created_at.date()) if wl.created_at else "",
            "day_of_week": wl.created_at.strftime("%A") if wl.created_at else "",
            "workout_type": wl.workout_type or "unknown",
            "completed": bool(wl.completed),
            "skipped": wl.completion_notes == "Skipped",
            "pain_reported": bool(wl.pain_reported),
            "muscle_groups": muscle_groups,
        })

    return {
        "yesterday_nutrition": yesterday_nutrition,
        "recent_workout_history": recent_workout_history,
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _should_nudge_water(user: User) -> str:
    """Return 'nudge_water' if user is behind on hydration, else ''."""
    target = user.daily_water_target_ml or 3000
    async with AsyncSessionLocal() as session:
        r = await session.execute(
            select(func.sum(WaterLog.amount_ml))
            .where(WaterLog.user_id == user.id)
            .where(WaterLog.logged_at >= _today_start())
        )
        consumed = r.scalar() or 0.0
    return "nudge_water" if consumed < target * 0.4 else ""


async def _run_parallel(*coros):
    """Run multiple coroutines concurrently."""
    import asyncio
    return await asyncio.gather(*coros)


def _format_plan(plan: dict) -> str:
    lines = [f"🏋️ *{plan.get('workout_type','Workout').upper()}*\n"]
    for ex in plan.get("main_workout", []):
        lines.append(
            f"• *{ex.get('exercise')}* — "
            f"{ex.get('sets',3)}×{ex.get('reps','10')} | rest {ex.get('rest_seconds',60)}s"
        )
    if tip := plan.get("coach_tip"):
        lines.append(f"\n💡 _{tip}_")
    return "\n".join(lines)
