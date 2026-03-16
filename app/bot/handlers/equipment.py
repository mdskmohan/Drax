"""
Gym equipment detection and management.
Supports: preset selection, manual text, and photo detection.
"""
import io
from telegram import Update
from telegram.ext import ContextTypes
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.user import User
from app.agents.fitness_coach import FitnessCoachAgent
from app.bot.keyboards import equipment_setup_keyboard, equipment_selection_keyboard, main_menu_keyboard

coach = FitnessCoachAgent()

EQUIPMENT_PRESETS = {
    "gym": [
        "barbell", "dumbbells", "cable machine", "smith machine",
        "bench", "lat pulldown", "leg press", "treadmill", "stationary bike",
    ],
    "home": ["dumbbells", "resistance bands", "pull-up bar", "bench"],
    "bodyweight": [],
}


async def equipment_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show equipment setup options."""
    query = update.callback_query
    if query:
        await query.answer()
        msg_fn = query.edit_message_text
    else:
        msg_fn = update.message.reply_text

    await msg_fn(
        "🏋️ *Gym Equipment Setup*\n\n"
        "Tell Drax what equipment you have access to — workouts will be customized accordingly.\n\n"
        "How do you want to set it up?",
        parse_mode="Markdown",
        reply_markup=equipment_setup_keyboard(),
    )


async def equipment_setup_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle equipment setup type selection."""
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data == "equip_setup_photo":
        context.user_data["awaiting_equipment_photo"] = True
        await query.edit_message_text(
            "📷 *Send a photo of your gym/home gym*\n\n"
            "I'll automatically detect all the equipment and customize your workouts!\n\n"
            "_Take a wide-angle photo showing all your equipment._",
            parse_mode="Markdown",
        )
        return

    setup_type = data.replace("equip_setup_", "")  # gym | home | bodyweight

    if setup_type == "bodyweight":
        await _save_equipment(user_id, [], "bodyweight")
        await query.edit_message_text(
            "✅ *Bodyweight setup saved!*\n\n"
            "Your workouts will use bodyweight exercises only — no equipment needed.\n\n"
            "Great choice! Bodyweight training is highly effective. 💪",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(),
        )
        return

    if setup_type == "gym":
        # Pre-load with full gym preset but let user customize
        context.user_data["selected_equipment"] = list(EQUIPMENT_PRESETS["gym"])
    else:
        context.user_data["selected_equipment"] = list(EQUIPMENT_PRESETS["home"])

    context.user_data["equipment_setup_type"] = setup_type
    selected = context.user_data["selected_equipment"]

    await query.edit_message_text(
        f"🏋️ *Select your equipment*\n\n"
        f"Tap to toggle items on/off. ✅ = included in your workouts.\n"
        f"Currently selected: {len(selected)} items",
        parse_mode="Markdown",
        reply_markup=equipment_selection_keyboard(selected),
    )


async def equipment_toggle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle individual equipment items in multi-select."""
    query = update.callback_query
    await query.answer()
    item = query.data.replace("equip_toggle_", "")

    selected = context.user_data.get("selected_equipment", [])
    if item in selected:
        selected.remove(item)
    else:
        selected.append(item)
    context.user_data["selected_equipment"] = selected

    await query.edit_message_text(
        f"🏋️ *Select your equipment*\n\n"
        f"Tap to toggle. ✅ = included.\n"
        f"Currently selected: {len(selected)} items",
        parse_mode="Markdown",
        reply_markup=equipment_selection_keyboard(selected),
    )


async def equipment_done_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Save the selected equipment list."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    selected = context.user_data.pop("selected_equipment", [])
    setup_type = context.user_data.pop("equipment_setup_type", "gym")

    await _save_equipment(user_id, selected, setup_type)

    items_text = "\n".join(f"• {item}" for item in selected) if selected else "• No equipment (bodyweight)"
    await query.edit_message_text(
        f"✅ *Equipment saved!*\n\n"
        f"Your workouts will now be customized for:\n{items_text}\n\n"
        f"Use /workout to get your personalized plan! 🏋️",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )


async def equipment_photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Handle a gym equipment photo and auto-detect equipment."""
    if not context.user_data.get("awaiting_equipment_photo"):
        return False

    context.user_data.pop("awaiting_equipment_photo", None)
    user_id = update.effective_user.id
    photo = update.message.photo[-1]

    processing_msg = await update.message.reply_text(
        "🔍 Scanning your gym equipment... This takes a few seconds!"
    )

    photo_file = await context.bot.get_file(photo.file_id)
    buf = io.BytesIO()
    await photo_file.download_to_memory(buf)
    image_bytes = buf.getvalue()

    result = await coach.scan_equipment_from_photo(image_bytes)
    equipment = result.get("equipment", [])
    setup_type = result.get("setup_type", "gym")

    if not equipment:
        await processing_msg.edit_text(
            "🤔 I couldn't clearly detect equipment from that photo.\n\n"
            "Try a clearer, wider-angle photo, or select equipment manually.",
            reply_markup=equipment_setup_keyboard(),
        )
        return True

    # Show detected equipment for confirmation
    context.user_data["selected_equipment"] = equipment
    context.user_data["equipment_setup_type"] = setup_type

    items_text = "\n".join(f"• {item}" for item in equipment)
    await processing_msg.edit_text(
        f"✅ *Equipment detected!*\n\n{items_text}\n\n"
        f"Tap to adjust if needed:",
        parse_mode="Markdown",
        reply_markup=equipment_selection_keyboard(equipment),
    )
    return True


async def _save_equipment(user_id: int, equipment: list[str], setup_type: str):
    """Save equipment to the database."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user:
            user.equipment_list = equipment
            user.equipment_setup = setup_type
            await session.commit()
    # Clear workout cache for this user so next plan uses new equipment
    from app.agents.fitness_coach import _workout_cache
    keys_to_delete = [k for k in _workout_cache if k[0] == user_id]
    for k in keys_to_delete:
        del _workout_cache[k]
