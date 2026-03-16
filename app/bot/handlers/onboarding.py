"""
Onboarding handlers — collect user profile through a conversational flow.
States: not_started → name → age → gender → height → weight → goal_weight
        → timeline → diet → workout_level → gym_days → gym_schedule
        → equipment → language → completed
"""
from telegram import Update
from telegram.ext import ContextTypes
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.user import User, OnboardingState
from app.bot.keyboards import (
    gender_keyboard, diet_keyboard, workout_level_keyboard,
    gym_days_keyboard, gym_schedule_keyboard, equipment_setup_keyboard,
    language_keyboard, main_menu_keyboard,
)


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
                "🏋️ *Welcome to Drax — Your AI Personal Fitness Coach!*\n\n"
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
            await update.message.reply_text("Let's continue your setup! 👇")
            await _prompt_current_state(update, user)


async def handle_onboarding_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_user = update.effective_user
    text = update.message.text.strip()

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.id == tg_user.id))
        user = result.scalar_one_or_none()

        if not user or user.onboarding_state == OnboardingState.completed:
            return False

        state = user.onboarding_state

        if state == OnboardingState.collecting_name:
            user.full_name = text
            user.first_name = text.split()[0]
            user.onboarding_state = OnboardingState.collecting_age
            await session.commit()
            await update.message.reply_text(
                f"Nice to meet you, *{user.first_name}*! 🎉\n\nHow old are you?",
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
                await update.message.reply_text("What is your gender?", reply_markup=gender_keyboard())
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
                    f"Got it — *{weight}kg* noted! 💪\n\nWhat is your *goal weight* in kg?",
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
                    f"So you want to lose *{diff}kg*! 🎯\n\nIn how many months? (e.g., 10)",
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
                    f"*{months} months* — solid! 🗓️\n\nWhat is your diet preference?",
                    parse_mode="Markdown",
                    reply_markup=diet_keyboard(),
                )
            except ValueError:
                await update.message.reply_text("Please enter months as a number (e.g., 10)")

        return True


async def handle_onboarding_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
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

        # ── Gender ──────────────────────────────────────────────────────────
        if state == OnboardingState.collecting_gender and data.startswith("gender_"):
            user.gender = data.replace("gender_", "")
            user.onboarding_state = OnboardingState.collecting_height
            await session.commit()
            await query.edit_message_text(
                f"Got it! ✅\n\nWhat is your *height* in cm? (e.g., 175)",
                parse_mode="Markdown",
            )
            return True

        # ── Diet ────────────────────────────────────────────────────────────
        elif state == OnboardingState.collecting_diet and data.startswith("diet_"):
            from app.models.user import DietPreference
            diet = data.replace("diet_", "")
            user.diet_preference = DietPreference(diet)
            user.onboarding_state = OnboardingState.collecting_workout_level
            await session.commit()
            await query.edit_message_text(
                f"*{diet.capitalize()}* diet — noted! 🥗\n\nWhat is your workout experience level?",
                parse_mode="Markdown",
                reply_markup=workout_level_keyboard(),
            )
            return True

        # ── Workout Level ────────────────────────────────────────────────────
        elif state == OnboardingState.collecting_workout_level and data.startswith("level_"):
            from app.models.user import WorkoutLevel
            level = data.replace("level_", "")
            user.workout_level = WorkoutLevel(level)
            user.onboarding_state = OnboardingState.collecting_gym_days
            await session.commit()
            await query.edit_message_text(
                f"*{level.capitalize()}* — perfect! 💪\n\nHow many days per week can you train?",
                parse_mode="Markdown",
                reply_markup=gym_days_keyboard(),
            )
            return True

        # ── Gym Days Count ───────────────────────────────────────────────────
        elif state == OnboardingState.collecting_gym_days and data.startswith("gym_"):
            days = int(data.replace("gym_", ""))
            user.gym_days_per_week = days
            user.onboarding_state = OnboardingState.collecting_gym_schedule
            await session.commit()
            # Initialize empty schedule in context
            context.user_data["onboarding_schedule"] = []
            await query.edit_message_text(
                f"*{days} days/week* — let's schedule them! 📅\n\n"
                f"Which days will you train? Tap to select:",
                parse_mode="Markdown",
                reply_markup=gym_schedule_keyboard([]),
            )
            return True

        # ── Gym Schedule (multi-select) ──────────────────────────────────────
        elif state == OnboardingState.collecting_gym_schedule:
            if data.startswith("schedule_") and not data == "schedule_done":
                day = data.replace("schedule_", "")
                schedule = context.user_data.get("onboarding_schedule", [])
                if day in schedule:
                    schedule.remove(day)
                else:
                    schedule.append(day)
                context.user_data["onboarding_schedule"] = schedule
                await query.edit_message_text(
                    f"📅 *Select your training days*\n"
                    f"Selected: {', '.join(schedule) if schedule else 'none'}\n\n"
                    f"Tap to toggle. Press Done when finished.",
                    parse_mode="Markdown",
                    reply_markup=gym_schedule_keyboard(schedule),
                )
                return True

            elif data == "schedule_done":
                schedule = context.user_data.pop("onboarding_schedule", [])
                user.gym_schedule = schedule
                user.onboarding_state = OnboardingState.collecting_equipment
                await session.commit()
                await query.edit_message_text(
                    f"✅ Schedule saved: {', '.join(schedule) if schedule else 'flexible'}!\n\n"
                    f"🏋️ Now let's set up your gym equipment so workouts are perfectly customized:",
                    parse_mode="Markdown",
                    reply_markup=equipment_setup_keyboard(),
                )
                return True

        # ── Equipment (during onboarding) ────────────────────────────────────
        elif state == OnboardingState.collecting_equipment:
            if data.startswith("equip_setup_") and data != "equip_setup_photo":
                setup_type = data.replace("equip_setup_", "")
                from app.bot.handlers.equipment import EQUIPMENT_PRESETS
                if setup_type == "bodyweight":
                    user.equipment_list = []
                    user.equipment_setup = "bodyweight"
                    user.onboarding_state = OnboardingState.collecting_language
                    await session.commit()
                    await query.edit_message_text(
                        "✅ Bodyweight only — noted!\n\n🌐 Last step: what language do you prefer?",
                        parse_mode="Markdown",
                        reply_markup=language_keyboard(),
                    )
                else:
                    context.user_data["selected_equipment"] = list(EQUIPMENT_PRESETS.get(setup_type, []))
                    context.user_data["equipment_setup_type"] = setup_type
                    selected = context.user_data["selected_equipment"]
                    from app.bot.keyboards import equipment_selection_keyboard
                    await query.edit_message_text(
                        f"Tap to toggle equipment. ✅ = included:\n{len(selected)} items pre-selected",
                        parse_mode="Markdown",
                        reply_markup=equipment_selection_keyboard(selected),
                    )
                return True

            elif data == "equip_setup_photo":
                context.user_data["awaiting_equipment_photo"] = True
                context.user_data["equipment_onboarding"] = True
                await query.edit_message_text(
                    "📷 Send a photo of your gym/home gym and I'll detect your equipment!",
                    parse_mode="Markdown",
                )
                return True

            elif data.startswith("equip_toggle_"):
                item = data.replace("equip_toggle_", "")
                selected = context.user_data.get("selected_equipment", [])
                if item in selected:
                    selected.remove(item)
                else:
                    selected.append(item)
                context.user_data["selected_equipment"] = selected
                from app.bot.keyboards import equipment_selection_keyboard
                await query.edit_message_text(
                    f"Tap to toggle. {len(selected)} items selected:",
                    parse_mode="Markdown",
                    reply_markup=equipment_selection_keyboard(selected),
                )
                return True

            elif data == "equip_done":
                selected = context.user_data.pop("selected_equipment", [])
                setup_type = context.user_data.pop("equipment_setup_type", "gym")
                user.equipment_list = selected
                user.equipment_setup = setup_type
                user.onboarding_state = OnboardingState.collecting_language
                await session.commit()
                await query.edit_message_text(
                    f"✅ Equipment saved ({len(selected)} items)!\n\n🌐 Last step: preferred language?",
                    parse_mode="Markdown",
                    reply_markup=language_keyboard(),
                )
                return True

        # ── Language ─────────────────────────────────────────────────────────
        elif state == OnboardingState.collecting_language and data.startswith("lang_"):
            lang = data.replace("lang_", "")
            user.language = lang
            user.onboarding_state = OnboardingState.completed

            # Calculate targets
            if user.tdee:
                user.daily_calorie_target = round(user.tdee - 500)
            else:
                user.daily_calorie_target = 1800
            user.calculate_macros()

            from app.agents.hydration_agent import HydrationAgent
            user.daily_water_target_ml = HydrationAgent().calculate_daily_target(user)

            if user.weight_to_lose_kg and user.timeline_months:
                user.weekly_weight_loss_target_kg = round(
                    user.weight_to_lose_kg / (user.timeline_months * 4.33), 2
                )

            await session.commit()

            lang_names = {"en": "English", "hi": "Hindi", "es": "Spanish", "fr": "French", "ar": "Arabic", "de": "German"}
            lang_name = lang_names.get(lang, "English")

            equip_count = len(user.equipment_list or [])
            equip_text = f"{equip_count} items detected" if equip_count > 0 else user.equipment_setup or "gym"
            schedule_text = ", ".join(user.gym_schedule or []) or "flexible"

            await query.edit_message_text(
                f"🎉 *Setup Complete, {user.first_name}!*\n\n"
                f"📏 Height: {user.height_cm}cm\n"
                f"⚖️ Current: {user.current_weight_kg}kg → Goal: {user.goal_weight_kg}kg\n"
                f"📉 To lose: {user.weight_to_lose_kg}kg in {user.timeline_months} months\n"
                f"🔥 Calories: *{user.daily_calorie_target} kcal/day*\n"
                f"💪 Protein: *{user.protein_target_g}g* | Carbs: *{user.carbs_target_g}g* | Fat: *{user.fat_target_g}g*\n"
                f"💧 Water: *{user.daily_water_target_ml}ml/day*\n"
                f"🏋️ Training: *{schedule_text}*\n"
                f"⚙️ Equipment: *{equip_text}*\n"
                f"🌐 Language: *{lang_name}*\n\n"
                f"Let's *crush this goal* together! 💪",
                parse_mode="Markdown",
                reply_markup=main_menu_keyboard(),
            )
            return True

    return False


async def _prompt_current_state(update: Update, user: User):
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
        OnboardingState.collecting_gym_schedule: ("Which days will you train?", gym_schedule_keyboard([])),
        OnboardingState.collecting_equipment: ("What equipment do you have?", equipment_setup_keyboard()),
        OnboardingState.collecting_language: ("What language do you prefer?", language_keyboard()),
    }
    prompt, keyboard = prompts.get(user.onboarding_state, ("Let's continue your setup!", None))
    kwargs = {"parse_mode": "Markdown"}
    if keyboard:
        kwargs["reply_markup"] = keyboard
    await update.message.reply_text(prompt, **kwargs)
