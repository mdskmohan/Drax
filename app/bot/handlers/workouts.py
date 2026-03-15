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
from app.agents.fitness_coach import FitnessCoachAgent
from app.agents.recovery_agent import RecoveryAgent
from app.bot.keyboards import workout_done_keyboard, main_menu_keyboard


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
        plan = await coach.generate_daily_workout(
            user,
            day_of_week=day_of_week,
            is_gym_day=True,
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

            await query.edit_message_text(
                "🎉 *BEAST MODE ACTIVATED!*\n\n"
                "You just crushed your workout! Every rep counts. "
                "Your body is changing right now. 💪\n\n"
                "Remember to:\n"
                "✅ Drink 500ml water now\n"
                "✅ Eat a protein-rich meal within 30 min\n"
                "✅ Rest and recover tonight",
                parse_mode="Markdown",
                reply_markup=main_menu_keyboard(),
            )

        elif data == "workout_partial":
            if workout_log:
                workout_log.completed = True
                workout_log.completion_notes = "Partial completion"
                workout_log.completed_at = datetime.now(timezone.utc)
            await session.commit()

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
