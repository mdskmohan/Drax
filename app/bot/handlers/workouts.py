"""
Workout handlers — generate, show, and log workout completions.
"""
from datetime import datetime, timezone, date
from telegram import Update
from telegram.ext import ContextTypes
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.user import User
from app.models.workout_log import WorkoutLog
from app.models.exercise_log import ExerciseLog
from app.agents.fitness_coach import FitnessCoachAgent
from app.agents.recovery_agent import RecoveryAgent
from app.bot.keyboards import (
    workout_done_keyboard, main_menu_keyboard,
    log_weights_prompt_keyboard, exercise_weight_actions_keyboard,
)


coach = FitnessCoachAgent()
recovery = RecoveryAgent()


async def show_todays_workout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate and display today's workout plan."""
    query = update.callback_query
    user_id = update.effective_user.id if not query else query.from_user.id

    if query:
        await query.answer()
        msg = await query.edit_message_text("🏋️ Generating your workout plan...")
    else:
        msg = await update.message.reply_text("🏋️ Generating your workout plan...")

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user or user.onboarding_state.value != "completed":
            await msg.edit_text("Please complete your profile setup first with /start")
            return

        day_of_week = datetime.now().strftime("%A")

        from app.graph.nodes import fetch_coaching_context
        coaching_ctx = await fetch_coaching_context(user_id)

        plan = await coach.generate_daily_workout(
            user,
            day_of_week=day_of_week,
            is_gym_day=True,
            yesterday_nutrition=coaching_ctx["yesterday_nutrition"],
            recent_workout_history=coaching_ctx["recent_workout_history"],
        )

        # Save workout log
        workout_log = WorkoutLog(
            user_id=user_id,
            workout_type=plan.get("workout_type"),
            workout_plan=plan,
            exercises=plan.get("main_workout", []),
            duration_minutes=plan.get("duration_minutes"),
            calories_burned=plan.get("calories_burned_estimate"),
            ai_generated_plan=plan.get("formatted_plan", ""),
            youtube_links=plan.get("youtube_links", {}),
            scheduled_date=datetime.now(timezone.utc),
        )
        session.add(workout_log)
        await session.commit()

        context.user_data["current_workout_id"] = workout_log.id

        # Format message
        formatted = plan.get("formatted_plan", "")
        if not formatted:
            formatted = _format_workout_plan(plan)

        # Add YouTube links
        yt_links = plan.get("youtube_links", {})
        if yt_links:
            formatted += "\n\n🎥 *Exercise Tutorials:*\n"
            for exercise, url in list(yt_links.items())[:3]:
                formatted += f"• [{exercise}]({url})\n"

        # Truncate if too long
        if len(formatted) > 3500:
            formatted = formatted[:3500] + "...\n\n_[Plan truncated]_"

        formatted += f"\n\n⏱️ Duration: {plan.get('duration_minutes', 45)} min"
        formatted += f"\n🔥 Est. calories burned: {plan.get('calories_burned_estimate', 300)} kcal"

        await msg.edit_text(
            formatted,
            parse_mode="Markdown",
            reply_markup=workout_done_keyboard(),
            disable_web_page_preview=True,
        )


async def _update_adaptation_incrementally(user_id: int, event: str, day_of_week: str) -> None:
    """
    Incrementally update adaptation_profile on every workout event using an
    Exponential Moving Average (α=0.15) — no need to wait until Sunday's batch.

    event: 'completed' | 'partial' | 'skipped'
    """
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            if not user:
                return

            profile = dict(user.adaptation_profile or {})

            # EMA on completion rate: new = 0.85 * old + 0.15 * outcome
            current_rate = profile.get("avg_workout_completion_rate", 0.75)
            outcome = 1.0 if event in ("completed", "partial") else 0.0
            profile["avg_workout_completion_rate"] = round(
                0.85 * current_rate + 0.15 * outcome, 3
            )

            # Intensity recommendation follows completion rate
            rate = profile["avg_workout_completion_rate"]
            profile["intensity_recommendation"] = (
                "high" if rate >= 0.85 else "moderate" if rate >= 0.65 else "low"
            )

            # Increment skip counter for this day (fractional to reduce noise;
            # weekly batch does the authoritative full-integer count)
            if event == "skipped":
                skips = dict(profile.get("skip_patterns", {}))
                skips[day_of_week] = round(skips.get(day_of_week, 0) + 0.5, 1)
                profile["skip_patterns"] = skips

            user.adaptation_profile = profile
            await session.commit()
    except Exception:
        pass  # never block the main completion flow


async def workout_completion_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle workout completion/skip/pain callbacks."""
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    workout_id = context.user_data.get("current_workout_id")

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if workout_id:
            wl_result = await session.execute(
                select(WorkoutLog).where(WorkoutLog.id == workout_id)
            )
            workout_log = wl_result.scalar_one_or_none()
        else:
            workout_log = None

        if data == "workout_done":
            if workout_log:
                workout_log.completed = True
                workout_log.completed_at = datetime.now(timezone.utc)
            await session.commit()

            import asyncio
            asyncio.create_task(
                _update_adaptation_incrementally(user_id, "completed", datetime.now().strftime("%A"))
            )

            # Store the main exercises for the weight-logging flow
            exercises = []
            if workout_log and workout_log.exercises:
                exercises = [
                    e.get("exercise", "") for e in workout_log.exercises
                    if e.get("exercise") and e.get("sets")  # skip bodyweight/cardio with no sets
                ]
            context.user_data["overload_exercises"] = exercises
            context.user_data["overload_index"] = 0
            context.user_data["overload_workout_id"] = workout_id

            await query.edit_message_text(
                "🎉 *Workout Complete!* 💪\n\n"
                "Great work! Log the weights you used to enable "
                "*progressive overload tracking* — next session will automatically "
                "suggest heavier weights.\n\n"
                "_Takes 30 seconds. Highly recommended._",
                parse_mode="Markdown",
                reply_markup=log_weights_prompt_keyboard(),
            )

        elif data == "workout_partial":
            if workout_log:
                workout_log.completed = True
                workout_log.completion_notes = "Partial completion"
                workout_log.completed_at = datetime.now(timezone.utc)
            await session.commit()

            import asyncio
            asyncio.create_task(
                _update_adaptation_incrementally(user_id, "partial", datetime.now().strftime("%A"))
            )

            await query.edit_message_text(
                "💪 *Partial workout logged!*\n\n"
                "Something is ALWAYS better than nothing. "
                "You showed up — that's what matters. "
                "Tomorrow we go full throttle! 🔥",
                parse_mode="Markdown",
                reply_markup=main_menu_keyboard(),
            )

        elif data == "workout_skipped":
            if workout_log:
                workout_log.completed = False
                workout_log.completion_notes = "Skipped"
            await session.commit()

            import asyncio
            asyncio.create_task(
                _update_adaptation_incrementally(user_id, "skipped", datetime.now().strftime("%A"))
            )

            await query.edit_message_text(
                "😤 *Workout skipped — noted.*\n\n"
                "Everyone has off days. The key is what you do TOMORROW.\n\n"
                "I've adjusted tomorrow's plan to make up for it. "
                "Set your alarm tonight! ⏰",
                parse_mode="Markdown",
                reply_markup=main_menu_keyboard(),
            )

        elif data == "workout_pain":
            if workout_log:
                workout_log.pain_reported = True
            await session.commit()
            context.user_data["awaiting_pain_description"] = True
            context.user_data["pain_workout_id"] = workout_id

            await query.edit_message_text(
                "🤕 *Pain/Injury Report*\n\n"
                "I'm sorry to hear that. Please describe what's hurting:\n\n"
                "_e.g., 'sharp pain in right knee during squats', 'lower back soreness'_",
                parse_mode="Markdown",
            )


async def handle_overload_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Handle overload_start / overload_next / overload_skip callbacks.
    Returns True if handled.
    """
    query = update.callback_query
    data = query.data
    if not data.startswith("overload_"):
        return False

    await query.answer()

    exercises = context.user_data.get("overload_exercises", [])
    idx = context.user_data.get("overload_index", 0)

    if data == "overload_skip" or not exercises:
        # Done — clear state, show main menu
        context.user_data.pop("overload_exercises", None)
        context.user_data.pop("overload_index", None)
        context.user_data.pop("overload_workout_id", None)
        context.user_data.pop("awaiting_exercise_weight", None)
        await query.edit_message_text(
            "✅ *All done!*\n\n"
            "Remember to:\n"
            "• Drink 500ml water\n"
            "• Eat protein within 30 min\n"
            "• Sleep 8 hours for recovery 💤",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(),
        )
        return True

    if data in ("overload_start", "overload_next"):
        if data == "overload_next":
            idx += 1
            context.user_data["overload_index"] = idx

        if idx >= len(exercises):
            # All exercises logged
            context.user_data.pop("overload_exercises", None)
            context.user_data.pop("overload_index", None)
            context.user_data.pop("awaiting_exercise_weight", None)
            await query.edit_message_text(
                "📊 *Weights logged!*\n\n"
                "Progressive overload data saved. Next session will suggest "
                "heavier weights automatically. 🏋️\n\n"
                "• Drink 500ml water\n"
                "• Eat protein within 30 min",
                parse_mode="Markdown",
                reply_markup=main_menu_keyboard(),
            )
            return True

        exercise_name = exercises[idx]
        remaining = len(exercises) - idx - 1
        context.user_data["awaiting_exercise_weight"] = exercise_name
        await query.edit_message_text(
            f"📊 *{exercise_name}*\n\n"
            f"What weight did you use? (e.g., `80kg`, `80`, or `bodyweight`)\n\n"
            f"_{remaining} exercise{'s' if remaining != 1 else ''} after this_",
            parse_mode="Markdown",
            reply_markup=exercise_weight_actions_keyboard(exercise_name, remaining),
        )

    return True


async def process_exercise_weight_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Handle free-text weight input during the progressive overload logging flow.
    Returns True if consumed.
    """
    exercise_name = context.user_data.get("awaiting_exercise_weight")
    if not exercise_name:
        return False

    text = update.message.text.strip().lower()
    context.user_data.pop("awaiting_exercise_weight", None)

    user_id = update.effective_user.id
    workout_id = context.user_data.get("overload_workout_id")

    # Parse weight
    weight_kg = None
    if text not in ("bodyweight", "bw", "none", "-"):
        import re
        m = re.search(r"(\d+(?:\.\d+)?)", text)
        if m:
            raw = float(m.group(1))
            # If > 300 assume lbs, convert
            weight_kg = round(raw * 0.453592, 1) if raw > 300 else raw

    # Parse reps/sets from workout plan if available
    exercises = context.user_data.get("overload_exercises", [])
    idx = context.user_data.get("overload_index", 0)
    plan_exercises = []
    if workout_id:
        async with AsyncSessionLocal() as session:
            wl = await session.execute(select(WorkoutLog).where(WorkoutLog.id == workout_id))
            wl_obj = wl.scalar_one_or_none()
            if wl_obj and wl_obj.exercises:
                plan_exercises = wl_obj.exercises

    sets, reps = None, None
    for ex in plan_exercises:
        if ex.get("exercise", "").lower() == exercise_name.lower():
            sets = ex.get("sets")
            reps_raw = ex.get("reps", "")
            if reps_raw:
                try:
                    reps = int(str(reps_raw).split("-")[0])
                except (ValueError, AttributeError):
                    pass
            break

    async with AsyncSessionLocal() as session:
        session.add(ExerciseLog(
            user_id=user_id,
            workout_log_id=workout_id,
            exercise_name=exercise_name,
            weight_kg=weight_kg,
            sets=sets,
            reps=reps,
        ))
        await session.commit()

    weight_display = f"{weight_kg}kg" if weight_kg else "bodyweight"
    sets_display = f"{sets}×{reps}" if sets and reps else ""
    await update.message.reply_text(
        f"✅ *{exercise_name}* — {sets_display} @ {weight_display} saved!",
        parse_mode="Markdown",
    )

    # Advance to next exercise
    idx += 1
    context.user_data["overload_index"] = idx
    if idx >= len(exercises):
        context.user_data.pop("overload_exercises", None)
        context.user_data.pop("overload_index", None)
        context.user_data.pop("overload_workout_id", None)
        await update.message.reply_text(
            "📊 *All weights logged!* Progressive overload data saved.\n\n"
            "Next workout will suggest progressive increases. 💪",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(),
        )
    else:
        next_exercise = exercises[idx]
        remaining = len(exercises) - idx - 1
        context.user_data["awaiting_exercise_weight"] = next_exercise
        await update.message.reply_text(
            f"📊 *{next_exercise}*\n\n"
            f"What weight? (e.g., `80kg` or `bodyweight`)\n"
            f"_{remaining} after this_",
            parse_mode="Markdown",
            reply_markup=exercise_weight_actions_keyboard(next_exercise, remaining),
        )

    return True


async def process_pain_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Process pain/injury description and generate modified workout."""
    if not context.user_data.get("awaiting_pain_description"):
        return False

    text = update.message.text.strip()
    user_id = update.effective_user.id
    context.user_data.pop("awaiting_pain_description", None)
    workout_id = context.user_data.pop("pain_workout_id", None)

    processing_msg = await update.message.reply_text("🩺 Assessing your pain report...")

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        # Update workout log
        if workout_id:
            wl_result = await session.execute(
                select(WorkoutLog).where(WorkoutLog.id == workout_id)
            )
            workout_log = wl_result.scalar_one_or_none()
            if workout_log:
                workout_log.pain_description = text
        await session.commit()

        # Extract structured pain data and store in adaptation_profile
        # so the AI gets precise avoidance rules ("avoid knee flexion under load")
        # rather than having to infer from raw text.
        if user:
            try:
                from app.services.llm import llm as _llm
                pain_structured = await _llm.json(
                    messages=[{"role": "user", "content": text}],
                    system=(
                        "Extract pain details from this description. "
                        'Return JSON: {"body_area": "e.g. lower back, right knee, left shoulder", '
                        '"severity": <1-10>, '
                        '"pain_type": "sharp|dull|soreness|stiffness|ache"}'
                    ),
                    fast=True,
                    max_tokens=80,
                )
                body_area = pain_structured.get("body_area", "").strip()
                severity = pain_structured.get("severity", 5)
                pain_type = pain_structured.get("pain_type", "soreness")

                if body_area:
                    profile = dict(user.adaptation_profile or {})
                    structured_list = list(profile.get("chronic_pain_structured", []))
                    structured_list.append({
                        "body_area": body_area,
                        "severity": int(severity),
                        "pain_type": pain_type,
                        "raw": text[:120],
                        "reported_at": datetime.now(timezone.utc).isoformat()[:10],
                    })
                    profile["chronic_pain_structured"] = structured_list[-10:]
                    user.adaptation_profile = profile
                    await session.commit()
            except Exception:
                pass  # never block the main pain assessment flow

        # Get pain assessment
        assessment = await recovery.assess_pain(user, text)
        modified_workout = await recovery.generate_modified_workout(user, assessment)

        severity = assessment.get("severity", "mild")
        see_doctor = assessment.get("see_doctor", False)
        recommendation = assessment.get("recommendation", "")

        response = (
            f"🩺 *Pain Assessment: {severity.upper()}*\n\n"
            f"⚠️ {recommendation}\n\n"
        )

        if see_doctor:
            response += "🏥 *Please see a doctor before training.*\n\n"

        response += f"💪 *Modified Workout Plan:*\n\n{modified_workout}"

        if len(response) > 3500:
            response = response[:3500] + "..."

        await processing_msg.edit_text(
            response,
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(),
        )

    return True


def _format_workout_plan(plan: dict) -> str:
    """Format a workout plan dict into readable text."""
    lines = [f"🏋️ *{plan.get('workout_type', 'Workout').upper()} PLAN*\n"]

    warmup = plan.get("warmup", [])
    if warmup:
        lines.append("*🔥 WARMUP:*")
        for ex in warmup:
            lines.append(f"• {ex.get('exercise')} — {ex.get('duration_seconds', 60)}s")
        lines.append("")

    main = plan.get("main_workout", [])
    if main:
        lines.append("*💪 MAIN WORKOUT:*")
        for ex in main:
            sets = ex.get("sets", 3)
            reps = ex.get("reps", "10")
            rest = ex.get("rest_seconds", 60)
            notes = ex.get("notes", "")
            lines.append(f"• *{ex.get('exercise')}*")
            lines.append(f"  {sets} sets × {reps} reps | Rest: {rest}s")
            if notes:
                lines.append(f"  _{notes}_")
        lines.append("")

    cooldown = plan.get("cooldown", [])
    if cooldown:
        lines.append("*🧘 COOLDOWN:*")
        for ex in cooldown:
            lines.append(f"• {ex.get('exercise')} — {ex.get('duration_seconds', 60)}s")
        lines.append("")

    tip = plan.get("coach_tip", "")
    if tip:
        lines.append(f"💡 *Coach Tip:* _{tip}_")

    return "\n".join(lines)
