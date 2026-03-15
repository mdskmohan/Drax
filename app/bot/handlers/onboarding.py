"""
Onboarding handlers — collect user profile through a conversational flow.
States: not_started → name → age → gender → height → weight → goal_weight
        → timeline → diet → workout_level → gym_days → completed
"""
from telegram import Update
from telegram.ext import ContextTypes

from app.database import AsyncSessionLocal
from app.models.user import User, OnboardingState
from app.bot.keyboards import (
    gender_keyboard, diet_keyboard, workout_level_keyboard,
    gym_days_keyboard, main_menu_keyboard,
)
from sqlalchemy import select


async def _get_or_create_user(telegram_id: int, tg_user) -> User:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.id == telegram_id))
        user = result.scalar_one_or_none()
        if not user:
            user = User(
                id=telegram_id,
                telegram_username=tg_user.username,
                first_name=tg_user.first_name,
                full_name=tg_user.full_name,
                onboarding_state=OnboardingState.not_started,
            )
            session.add(user)
            await session.commit()
        return user


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start — begin onboarding or show main menu."""
    tg_user = update.effective_user
    telegram_id = tg_user.id

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.id == telegram_id))
        user = result.scalar_one_or_none()

        if not user:
            user = User(
                id=telegram_id,
                telegram_username=tg_user.username,
                first_name=tg_user.first_name,
                full_name=tg_user.full_name,
                onboarding_state=OnboardingState.collecting_name,
            )
            session.add(user)
            await session.commit()

            await update.message.reply_text(
                "🏋️ *Welcome to FitBot — Your AI Personal Fitness Coach!*\n\n"
                "I'm here to help you lose weight, build strength, and transform your life.\n\n"
                "Let's get started with a quick setup (takes 2 minutes).\n\n"
                "👋 What's your *full name*?",
                parse_mode="Markdown",
            )
        elif user.onboarding_state == OnboardingState.completed:
            await update.message.reply_text(
                f"Welcome back, {user.first_name}! 💪\n\nWhat would you like to do today?",
                reply_markup=main_menu_keyboard(),
            )
        else:
            await update.message.reply_text(
                "Let's continue your setup! 👇",
            )
            await _prompt_current_state(update, user)


async def handle_onboarding_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Route text messages to the correct onboarding step."""
    tg_user = update.effective_user
    text = update.message.text.strip()

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.id == tg_user.id))
        user = result.scalar_one_or_none()

        if not user or user.onboarding_state == OnboardingState.completed:
            return False  # Not in onboarding

        state = user.onboarding_state

        if state == OnboardingState.collecting_name:
            user.full_name = text
            user.first_name = text.split()[0]
            user.onboarding_state = OnboardingState.collecting_age
            await session.commit()
            await update.message.reply_text(
                f"Nice to meet you, *{user.first_name}*! 🎉\n\nHow old are you? (Enter a number)",
                parse_mode="Markdown",
            )

        elif state == OnboardingState.collecting_age:
            try:
                age = int(text)
                if not 10 <= age <= 100:
                    raise ValueError
                user.age = age
                user.onboarding_state = OnboardingState.collecting_gender
                await session.commit()
                await update.message.reply_text(
                    "What is your gender?",
                    reply_markup=gender_keyboard(),
                )
            except ValueError:
                await update.message.reply_text("Please enter a valid age (e.g., 28)")

        elif state == OnboardingState.collecting_height:
            try:
                height = float(text.replace("cm", "").strip())
                if not 100 <= height <= 250:
                    raise ValueError
                user.height_cm = height
                user.onboarding_state = OnboardingState.collecting_weight
                await session.commit()
                await update.message.reply_text(
                    "What is your *current weight* in kg? (e.g., 95.5)",
                    parse_mode="Markdown",
                )
            except ValueError:
                await update.message.reply_text("Please enter height in cm (e.g., 175)")

        elif state == OnboardingState.collecting_weight:
            try:
                weight = float(text.replace("kg", "").strip())
                if not 30 <= weight <= 300:
                    raise ValueError
                user.current_weight_kg = weight
                user.onboarding_state = OnboardingState.collecting_goal_weight
                await session.commit()
                await update.message.reply_text(
                    f"Got it — *{weight}kg* noted! 💪\n\n"
                    "What is your *goal weight* in kg? (e.g., 75)",
                    parse_mode="Markdown",
                )
            except ValueError:
                await update.message.reply_text("Please enter weight in kg (e.g., 95.5)")

        elif state == OnboardingState.collecting_goal_weight:
            try:
                goal = float(text.replace("kg", "").strip())
                if not 30 <= goal <= 300:
                    raise ValueError
                user.goal_weight_kg = goal
                user.onboarding_state = OnboardingState.collecting_timeline
                await session.commit()
                diff = round(user.current_weight_kg - goal, 1)
                await update.message.reply_text(
                    f"So you want to lose *{diff}kg*! That's a great goal! 🎯\n\n"
                    "In how many months do you want to achieve this? (e.g., 10)",
                    parse_mode="Markdown",
                )
            except ValueError:
                await update.message.reply_text("Please enter goal weight in kg (e.g., 75)")

        elif state == OnboardingState.collecting_timeline:
            try:
                months = int(text.replace("months", "").strip())
                if not 1 <= months <= 36:
                    raise ValueError
                user.timeline_months = months
                user.onboarding_state = OnboardingState.collecting_diet
                await session.commit()
                await update.message.reply_text(
                    f"*{months} months* — solid timeline! 🗓️\n\n"
                    "What is your diet preference?",
                    parse_mode="Markdown",
                    reply_markup=diet_keyboard(),
                )
            except ValueError:
                await update.message.reply_text("Please enter months as a number (e.g., 10)")

        return True  # Was handled as onboarding


async def handle_onboarding_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Handle inline keyboard callbacks during onboarding."""
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            return False

        state = user.onboarding_state

        if state == OnboardingState.collecting_gender and data.startswith("gender_"):
            gender = data.replace("gender_", "")
            user.gender = gender
            user.onboarding_state = OnboardingState.collecting_height
            await session.commit()
            await query.edit_message_text(
                f"Got it — *{gender}* noted! ✅\n\n"
                "What is your *height* in cm? (e.g., 175)",
                parse_mode="Markdown",
            )
            return True

        elif state == OnboardingState.collecting_diet and data.startswith("diet_"):
            from app.models.user import DietPreference
            diet = data.replace("diet_", "")
            user.diet_preference = DietPreference(diet)
            user.onboarding_state = OnboardingState.collecting_workout_level
            await session.commit()
            await query.edit_message_text(
                f"*{diet.capitalize()}* diet — noted! 🥗\n\n"
                "What is your current workout experience level?",
                parse_mode="Markdown",
                reply_markup=workout_level_keyboard(),
            )
            return True

        elif state == OnboardingState.collecting_workout_level and data.startswith("level_"):
            from app.models.user import WorkoutLevel
            level = data.replace("level_", "")
            user.workout_level = WorkoutLevel(level)
            user.onboarding_state = OnboardingState.collecting_gym_days
            await session.commit()
            await query.edit_message_text(
                f"*{level.capitalize()}* level — perfect! 💪\n\n"
                "How many days per week can you train at the gym?",
                parse_mode="Markdown",
                reply_markup=gym_days_keyboard(),
            )
            return True

        elif state == OnboardingState.collecting_gym_days and data.startswith("gym_"):
            days = int(data.replace("gym_", ""))
            user.gym_days_per_week = days
            user.onboarding_state = OnboardingState.completed

            # Calculate and set targets
            if user.tdee:
                user.daily_calorie_target = round(user.tdee - 500)
            else:
                user.daily_calorie_target = 1800

            from app.agents.hydration_agent import HydrationAgent
            hydration = HydrationAgent()
            user.daily_water_target_ml = hydration.calculate_daily_target(user)

            if user.weight_to_lose_kg and user.timeline_months:
                user.weekly_weight_loss_target_kg = round(
                    user.weight_to_lose_kg / (user.timeline_months * 4.33), 2
                )

            await session.commit()

            # Final onboarding summary
            await query.edit_message_text(
                f"🎉 *Setup Complete, {user.first_name}!*\n\n"
                f"Here's your personalized plan:\n\n"
                f"📏 Height: {user.height_cm}cm\n"
                f"⚖️ Current: {user.current_weight_kg}kg → Goal: {user.goal_weight_kg}kg\n"
                f"📉 To lose: {user.weight_to_lose_kg}kg in {user.timeline_months} months\n"
                f"🔥 Daily calorie target: *{user.daily_calorie_target} kcal*\n"
                f"💧 Daily water target: *{user.daily_water_target_ml}ml*\n"
                f"🏋️ Gym: *{user.gym_days_per_week} days/week*\n"
                f"📈 Target: *{user.weekly_weight_loss_target_kg}kg/week*\n\n"
                f"Let's *crush this goal* together! 💪",
                parse_mode="Markdown",
                reply_markup=main_menu_keyboard(),
            )
            return True

    return False


async def _prompt_current_state(update: Update, user: User):
    """Re-prompt based on current onboarding state."""
    prompts = {
        OnboardingState.collecting_name: ("What's your full name?", None),
        OnboardingState.collecting_age: ("How old are you?", None),
        OnboardingState.collecting_gender: ("What's your gender?", gender_keyboard()),
        OnboardingState.collecting_height: ("What's your height in cm?", None),
        OnboardingState.collecting_weight: ("What's your current weight in kg?", None),
        OnboardingState.collecting_goal_weight: ("What's your goal weight in kg?", None),
        OnboardingState.collecting_timeline: ("How many months for your goal?", None),
        OnboardingState.collecting_diet: ("What's your diet preference?", diet_keyboard()),
        OnboardingState.collecting_workout_level: ("What's your workout level?", workout_level_keyboard()),
        OnboardingState.collecting_gym_days: ("How many gym days per week?", gym_days_keyboard()),
    }
    prompt, keyboard = prompts.get(user.onboarding_state, ("Let's continue your setup!", None))
    kwargs = {"parse_mode": "Markdown"}
    if keyboard:
        kwargs["reply_markup"] = keyboard
    await update.message.reply_text(prompt, **kwargs)
