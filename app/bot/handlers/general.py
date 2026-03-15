"""
General command handlers — /help, /menu, /plan, /motivation, /settings, etc.
"""
from datetime import datetime, timezone
from telegram import Update
from telegram.ext import ContextTypes
from sqlalchemy import select, func

from app.database import AsyncSessionLocal
from app.models.user import User
from app.models.meal_log import MealLog
from app.models.water_log import WaterLog
from app.agents.motivation_agent import MotivationAgent
from app.agents.nutrition_agent import NutritionAgent
from app.bot.keyboards import main_menu_keyboard


motivation_agent = MotivationAgent()
nutrition_agent = NutritionAgent()


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏋️ *Drax Commands*\n\n"
        "*/start* — Setup or return to main menu\n"
        "*/menu* — Show main menu\n"
        "*/plan* — Get today's full plan\n"
        "*/meal* — Log a meal\n"
        "*/water* — Log water intake\n"
        "*/workout* — Today's workout\n"
        "*/weight* — Log your weight\n"
        "*/progress* — View your progress\n"
        "*/report* — Weekly progress report\n"
        "*/motivation* — Get motivation\n"
        "*/help* — Show this message\n\n"
        "You can also just *send text* describing your meal anytime!",
        parse_mode="Markdown",
    )


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "What would you like to do? 👇",
        reply_markup=main_menu_keyboard(),
    )


async def daily_plan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send today's full plan — meals + workout + water target."""
    query = update.callback_query
    user_id = update.effective_user.id if not query else query.from_user.id

    if query:
        await query.answer()
        msg = await query.edit_message_text("📋 Building your daily plan...")
    else:
        msg = await update.message.reply_text("📋 Building your daily plan...")

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user or user.onboarding_state.value != "completed":
            await msg.edit_text("Please complete your profile setup first with /start")
            return

        # Generate meal plan
        meal_plan = await nutrition_agent.generate_daily_meal_plan(user)

        today = datetime.now().strftime("%A, %B %d")
        calorie_target = user.daily_calorie_target or 2000
        water_target = user.daily_water_target_ml or 3000

        plan_text = (
            f"📋 *Daily Plan — {today}*\n\n"
            f"🎯 Calorie target: *{calorie_target} kcal*\n"
            f"💧 Water target: *{water_target}ml*\n\n"
            f"━━━━━━━━━━━━━━━━\n\n"
        )

        # Meal plan
        meals = meal_plan.get("meals", {})
        if meals:
            plan_text += "🍽️ *MEAL PLAN:*\n\n"
            meal_emojis = {
                "breakfast": "🌅",
                "lunch": "☀️",
                "dinner": "🌙",
                "snacks": "🍎",
            }
            for meal_name, meal_data in meals.items():
                if isinstance(meal_data, dict):
                    emoji = meal_emojis.get(meal_name, "🍽️")
                    plan_text += (
                        f"{emoji} *{meal_name.capitalize()}*\n"
                        f"   {meal_data.get('description', '')}\n"
                        f"   🔥 {meal_data.get('calories', 0):.0f} kcal | "
                        f"💪 {meal_data.get('protein_g', 0):.0f}g protein\n\n"
                    )

        plan_text += f"━━━━━━━━━━━━━━━━\n\n"
        plan_text += f"💡 *Tip:* {meal_plan.get('nutrition_tip', 'Stay consistent!')}\n\n"
        plan_text += f"Use /workout to get today's workout plan! 🏋️"

        if len(plan_text) > 4000:
            plan_text = plan_text[:4000] + "..."

        await msg.edit_text(
            plan_text,
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(),
        )


async def motivation_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a motivational message + optional video."""
    query = update.callback_query
    user_id = update.effective_user.id if not query else query.from_user.id

    if query:
        await query.answer()
        msg = await query.edit_message_text("💪 Loading your motivation...")
    else:
        msg = await update.message.reply_text("💪 Loading your motivation...")

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if user:
            motivation_text = await motivation_agent.get_morning_motivation(user)
        else:
            motivation_text = motivation_agent.get_daily_quote()

        # Try to get a YouTube video
        video = await motivation_agent.get_motivation_video()

        full_text = f"💪 *Daily Motivation*\n\n{motivation_text}"

        if video:
            full_text += f"\n\n🎥 [{video['title']}]({video['url']})"

        if len(full_text) > 4000:
            full_text = full_text[:4000]

        await msg.edit_text(
            full_text,
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(),
            disable_web_page_preview=False,
        )


async def unknown_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Smart fallback — try to detect if user is logging food or water
    when they send free-form text.
    """
    text = update.message.text.lower().strip()

    # Water keywords
    water_keywords = ["ml", "glass", "glasses", "bottle", "water", "drank", "drink", "litre", "liter"]
    if any(kw in text for kw in water_keywords):
        from app.agents.hydration_agent import HydrationAgent
        agent = HydrationAgent()
        amount = agent.parse_water_amount(text)
        if amount:
            context.user_data.pop("awaiting_meal_input", None)
            from app.bot.handlers.water import _log_and_respond
            await _log_and_respond(update.effective_user.id, amount, message=update.message)
            return

    # Food keywords — treat as meal log
    food_keywords = ["ate", "had", "eat", "eating", "lunch", "dinner", "breakfast", "snack", "food"]
    is_food = any(kw in text for kw in food_keywords) or len(text.split()) > 2

    if is_food and not text.startswith("/"):
        context.user_data["awaiting_meal_input"] = True
        context.user_data["pending_meal_type"] = _detect_meal_type(text)
        from app.bot.handlers.meals import process_meal_text
        await process_meal_text(update, context)
        return

    # Default
    await update.message.reply_text(
        "I didn't quite understand that. 🤔\n\n"
        "Use the menu below or type /help for commands:",
        reply_markup=main_menu_keyboard(),
    )


def _detect_meal_type(text: str) -> str:
    text = text.lower()
    if any(w in text for w in ["breakfast", "morning", "oats", "cereal"]):
        return "breakfast"
    if any(w in text for w in ["lunch", "afternoon"]):
        return "lunch"
    if any(w in text for w in ["dinner", "supper", "night"]):
        return "dinner"
    return "snack"
