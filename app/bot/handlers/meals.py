"""
Meal logging handlers.
Supports text input, quick logging, and photo food detection.
"""
from datetime import datetime, timezone
from telegram import Update
from telegram.ext import ContextTypes
from sqlalchemy import select, func

from app.database import AsyncSessionLocal
from app.models.user import User
from app.models.meal_log import MealLog
from app.agents.nutrition_agent import NutritionAgent
from app.bot.keyboards import meal_type_keyboard, main_menu_keyboard


nutrition_agent = NutritionAgent()


async def log_meal_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Prompt user to select meal type."""
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text(
            "🍽️ *Log a Meal*\n\nWhat type of meal is this?",
            parse_mode="Markdown",
            reply_markup=meal_type_keyboard(),
        )
    else:
        await update.message.reply_text(
            "🍽️ *Log a Meal*\n\nWhat type of meal is this?",
            parse_mode="Markdown",
            reply_markup=meal_type_keyboard(),
        )


async def meal_type_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Store selected meal type and ask for food description."""
    query = update.callback_query
    await query.answer()
    meal_type = query.data.replace("meal_", "")
    context.user_data["pending_meal_type"] = meal_type

    await query.edit_message_text(
        f"🍽️ *{meal_type.capitalize()} log*\n\n"
        f"Describe what you ate:\n\n"
        f"Examples:\n"
        f"• _2 eggs, toast with butter, orange juice_\n"
        f"• _chicken rice bowl with salad_\n"
        f"• _200g oats with milk and banana_\n\n"
        f"You can also send a *photo* of your food! 📷",
        parse_mode="Markdown",
    )
    context.user_data["awaiting_meal_input"] = True


async def process_meal_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Process a text meal log."""
    if not context.user_data.get("awaiting_meal_input"):
        return False

    text = update.message.text.strip()
    user_id = update.effective_user.id
    meal_type = context.user_data.pop("pending_meal_type", "snack")
    context.user_data.pop("awaiting_meal_input", None)

    # Send "processing" indicator
    processing_msg = await update.message.reply_text("🔍 Analyzing your meal...")

    async with AsyncSessionLocal() as session:
        # Get user
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            await processing_msg.edit_text("Please /start first to set up your profile.")
            return True

        # Parse nutrition
        nutrition = await nutrition_agent.parse_meal(user, text)

        # Get today's calories
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        cal_result = await session.execute(
            select(func.sum(MealLog.calories))
            .where(MealLog.user_id == user_id)
            .where(MealLog.logged_at >= today_start)
        )
        today_calories = cal_result.scalar() or 0.0

        # Get AI feedback
        feedback = await nutrition_agent.get_meal_feedback(
            user, text, nutrition,
            today_calories + nutrition.get("total_calories", 0)
        )

        # Save to database
        meal_log = MealLog(
            user_id=user_id,
            meal_type=meal_type,
            food_description=text,
            parsed_foods=nutrition.get("foods", []),
            calories=nutrition.get("total_calories", 0),
            protein_g=nutrition.get("total_protein_g", 0),
            carbs_g=nutrition.get("total_carbs_g", 0),
            fat_g=nutrition.get("total_fat_g", 0),
            fiber_g=nutrition.get("total_fiber_g", 0),
            sodium_mg=nutrition.get("total_sodium_mg", 0),
            source="text",
            ai_feedback=feedback,
        )
        session.add(meal_log)
        await session.commit()

        # Calculate totals for today
        new_total = today_calories + nutrition.get("total_calories", 0)
        remaining = (user.daily_calorie_target or 2000) - new_total

        cal = nutrition.get("total_calories", 0)
        protein = nutrition.get("total_protein_g", 0)
        carbs = nutrition.get("total_carbs_g", 0)
        fat = nutrition.get("total_fat_g", 0)

        await processing_msg.edit_text(
            f"✅ *{meal_type.capitalize()} logged!*\n\n"
            f"📊 *Nutrition:*\n"
            f"🔥 Calories: *{cal:.0f} kcal*\n"
            f"💪 Protein: {protein:.1f}g\n"
            f"🌾 Carbs: {carbs:.1f}g\n"
            f"🧈 Fat: {fat:.1f}g\n\n"
            f"📈 *Today's Total:* {new_total:.0f} / {user.daily_calorie_target or 2000} kcal\n"
            f"{'✅' if remaining >= 0 else '⚠️'} Remaining: {remaining:.0f} kcal\n\n"
            f"💬 *Coach says:*\n_{feedback}_",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(),
        )

    return True


async def process_meal_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process a food photo — use caption as description or AI vision."""
    user_id = update.effective_user.id
    photo = update.message.photo[-1]  # highest resolution
    caption = update.message.caption or "food in the photo"

    processing_msg = await update.message.reply_text(
        "📷 Analyzing your food photo..."
    )

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            await processing_msg.edit_text("Please /start first.")
            return

        # Use caption or a basic description for Nutritionix lookup
        food_description = caption if caption != "food in the photo" else "mixed food plate"
        nutrition = await nutrition_agent.parse_meal(user, food_description)

        meal_log = MealLog(
            user_id=user_id,
            meal_type=context.user_data.pop("pending_meal_type", "snack"),
            food_description=food_description,
            parsed_foods=nutrition.get("foods", []),
            calories=nutrition.get("total_calories", 0),
            protein_g=nutrition.get("total_protein_g", 0),
            carbs_g=nutrition.get("total_carbs_g", 0),
            fat_g=nutrition.get("total_fat_g", 0),
            source="photo",
            photo_file_id=photo.file_id,
        )
        session.add(meal_log)
        await session.commit()

        cal = nutrition.get("total_calories", 0)
        await processing_msg.edit_text(
            f"📷 *Food photo logged!*\n\n"
            f"Detected: _{food_description}_\n"
            f"🔥 Estimated calories: *{cal:.0f} kcal*\n\n"
            f"_Tip: Add a caption to your photo for more accurate tracking!_",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(),
        )


async def show_todays_meals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show today's meal summary."""
    user_id = update.effective_user.id
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        meals_result = await session.execute(
            select(MealLog)
            .where(MealLog.user_id == user_id)
            .where(MealLog.logged_at >= today_start)
            .order_by(MealLog.logged_at)
        )
        meals = meals_result.scalars().all()

        if not meals:
            await update.message.reply_text(
                "No meals logged today yet! 🍽️\n\nLog your first meal to get started.",
                reply_markup=main_menu_keyboard(),
            )
            return

        total_cal = sum(m.calories for m in meals)
        total_protein = sum(m.protein_g for m in meals)
        total_carbs = sum(m.carbs_g for m in meals)
        total_fat = sum(m.fat_g for m in meals)
        target = user.daily_calorie_target or 2000
        remaining = target - total_cal

        meal_lines = []
        for m in meals:
            time_str = m.logged_at.strftime("%H:%M") if m.logged_at else "?"
            meal_lines.append(
                f"• [{time_str}] *{m.meal_type or 'meal'}*: {m.food_description[:40]} "
                f"({m.calories:.0f} kcal)"
            )

        msg = (
            f"📋 *Today's Meals*\n\n"
            + "\n".join(meal_lines) +
            f"\n\n━━━━━━━━━━━━\n"
            f"🔥 Total: *{total_cal:.0f}* / *{target}* kcal\n"
            f"💪 Protein: {total_protein:.1f}g | Carbs: {total_carbs:.1f}g | Fat: {total_fat:.1f}g\n"
            f"{'✅ ' if remaining >= 0 else '⚠️ '}"
            f"{'Remaining: ' + str(round(remaining)) + ' kcal' if remaining >= 0 else 'Over budget by ' + str(round(abs(remaining))) + ' kcal'}"
        )

        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=main_menu_keyboard())
