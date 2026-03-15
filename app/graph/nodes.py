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
    """Generate today's workout plan."""
    user = state["user"]
    day = datetime.now().strftime("%A")

    plan = await _coach.generate_daily_workout(user, day_of_week=day, is_gym_day=True)

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
        await session.commit()

    change = (old_weight - weight) if old_weight else 0
    bar = ""
    if user.goal_weight_kg and old_weight:
        bar = "\n" + _progress.build_progress_bar(weight, old_weight, user.goal_weight_kg) + "\n"

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
    user = state["user"]
    day = datetime.now().strftime("%A, %B %d")
    week_day = datetime.now().strftime("%A")

    meal_plan, workout_plan = await _run_parallel(
        _nutrition.generate_daily_meal_plan(user),
        _coach.generate_daily_workout(user, day_of_week=week_day),
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
    from app.services.llm import llm
    user = state["user"]
    user_input = state.get("user_input", "")

    response = await llm.fast(
        messages=[{"role": "user", "content": user_input}],
        system=(
            f"You are Drax, an AI fitness coach on Telegram. "
            f"The user is {user.first_name if user else 'a user'}. "
            f"Answer their question briefly and helpfully. "
            f"If it's a greeting, respond warmly and ask how you can help with their fitness."
        ),
        max_tokens=300,
    )
    return {"response": response, "chain_to": ""}


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
