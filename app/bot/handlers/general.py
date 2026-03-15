"""
General command handlers — /help, /menu, /plan, /motivation, /settings, etc.
"""
from telegram import Update
from telegram.ext import ContextTypes

from app.graph import drax_graph
from app.bot.keyboards import main_menu_keyboard


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
    """Send today's full plan — routed through the graph."""
    query = update.callback_query
    user_id = update.effective_user.id if not query else query.from_user.id

    if query:
        await query.answer()
        msg = await query.edit_message_text("📋 Building your daily plan...")
    else:
        msg = await update.message.reply_text("📋 Building your daily plan...")

    result = await drax_graph.ainvoke({
        "user_id": user_id,
        "user_input": "get full plan",
        "intent": "get_plan",   # skip supervisor for explicit commands
    })

    response = result.get("response", "Something went wrong. Try again.")
    if len(response) > 4000:
        response = response[:4000] + "..."

    await msg.edit_text(response, parse_mode="Markdown",
                        reply_markup=main_menu_keyboard(),
                        disable_web_page_preview=True)


async def motivation_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a motivational message — routed through the graph."""
    query = update.callback_query
    user_id = update.effective_user.id if not query else query.from_user.id

    if query:
        await query.answer()
        msg = await query.edit_message_text("💪 Loading your motivation...")
    else:
        msg = await update.message.reply_text("💪 Loading your motivation...")

    result = await drax_graph.ainvoke({
        "user_id": user_id,
        "user_input": "motivate me",
        "intent": "get_motivation",
    })

    full_text = result.get("response", "You've got this! 💪")
    if len(full_text) > 4000:
        full_text = full_text[:4000]

    await msg.edit_text(
            full_text,
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(),
            disable_web_page_preview=False,
        )


async def unknown_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Route all free-form text through the LangGraph graph."""
    user_id = update.effective_user.id
    text = update.message.text.strip()

    msg = await update.message.reply_text("⏳ Thinking...")

    result = await drax_graph.ainvoke({
        "user_id": user_id,
        "user_input": text,
    })

    response = result.get("response", "I didn't quite understand that. Try /help for commands.")
    if len(response) > 4000:
        response = response[:4000] + "..."

    await msg.edit_text(response, parse_mode="Markdown",
                        reply_markup=main_menu_keyboard(),
                        disable_web_page_preview=True)


