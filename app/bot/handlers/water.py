"""
Water intake tracking handlers.
"""
from datetime import datetime, timezone
from telegram import Update
from telegram.ext import ContextTypes
from sqlalchemy import select, func

from app.database import AsyncSessionLocal
from app.models.user import User
from app.models.water_log import WaterLog
from app.agents.hydration_agent import HydrationAgent
from app.graph import drax_graph
from app.bot.keyboards import water_quick_keyboard, main_menu_keyboard


hydration_agent = HydrationAgent()  # kept for _log_and_respond helper


async def log_water_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show water quick-log buttons."""
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text(
            "💧 *Log Water Intake*\n\nHow much water did you drink?",
            parse_mode="Markdown",
            reply_markup=water_quick_keyboard(),
        )
    else:
        await update.message.reply_text(
            "💧 *Log Water Intake*\n\nHow much water did you drink?",
            parse_mode="Markdown",
            reply_markup=water_quick_keyboard(),
        )


async def water_amount_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle quick water log buttons (250, 500, 750, 1000ml)."""
    query = update.callback_query
    await query.answer()
    data = query.data  # e.g. "water_250"

    if data == "water_custom":
        context.user_data["awaiting_water_input"] = True
        await query.edit_message_text(
            "💧 Enter the amount you drank:\n\n"
            "Examples: _500ml_, _2 glasses_, _1L_, _1 bottle_",
            parse_mode="Markdown",
        )
        return

    amount_ml = int(data.replace("water_", ""))
    await _log_and_respond(query.from_user.id, amount_ml, query=query)


async def process_water_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Process custom water amount text via LangGraph."""
    if not context.user_data.get("awaiting_water_input"):
        return False

    text = update.message.text.strip()
    context.user_data.pop("awaiting_water_input", None)

    processing_msg = await update.message.reply_text("💧 Logging water...")

    result = await drax_graph.ainvoke({
        "user_id": update.effective_user.id,
        "user_input": text,
        "intent": "log_water",
    })

    response = result.get("response", "💧 Water logged!")
    await processing_msg.edit_text(
        response,
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )
    return True


async def _log_and_respond(user_id: int, amount_ml: int, query=None, message=None):
    """Log water intake and send hydration status."""
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            return

        # Log water
        log = WaterLog(user_id=user_id, amount_ml=amount_ml)
        session.add(log)
        await session.flush()

        # Get today's total
        total_result = await session.execute(
            select(func.sum(WaterLog.amount_ml))
            .where(WaterLog.user_id == user_id)
            .where(WaterLog.logged_at >= today_start)
        )
        today_total = total_result.scalar() or 0.0
        await session.commit()

        target = user.daily_water_target_ml or 3000
        status = hydration_agent.get_hydration_status(int(today_total), target)
        progress_bar = hydration_agent.format_progress_bar(int(today_total), target)

        text = (
            f"💧 *+{amount_ml}ml logged!*\n\n"
            f"Today: *{today_total:.0f}ml* / *{target}ml*\n"
            f"{progress_bar}\n\n"
            f"{status['emoji']} {status['message']}\n\n"
            f"🥛 Glasses today: {status['glasses']}"
        )

        if query:
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=main_menu_keyboard())
        elif message:
            await message.reply_text(text, parse_mode="Markdown", reply_markup=main_menu_keyboard())


async def show_water_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current water intake status."""
    user_id = update.effective_user.id
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        total_result = await session.execute(
            select(func.sum(WaterLog.amount_ml))
            .where(WaterLog.user_id == user_id)
            .where(WaterLog.logged_at >= today_start)
        )
        today_total = total_result.scalar() or 0.0
        target = (user.daily_water_target_ml or 3000) if user else 3000

        status = hydration_agent.get_hydration_status(int(today_total), target)
        progress_bar = hydration_agent.format_progress_bar(int(today_total), target)

        await update.message.reply_text(
            f"💧 *Hydration Status*\n\n"
            f"Today: *{today_total:.0f}ml* / *{target}ml*\n"
            f"{progress_bar}\n\n"
            f"{status['emoji']} {status['message']}",
            parse_mode="Markdown",
            reply_markup=water_quick_keyboard(),
        )
