"""
Telegram inline and reply keyboards for common interactions.
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup


# ── Main Menu ──────────────────────────────────────────────────────────────────

def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🍽️ Log Meal", callback_data="log_meal"),
            InlineKeyboardButton("💧 Log Water", callback_data="log_water"),
        ],
        [
            InlineKeyboardButton("🏋️ Today's Workout", callback_data="todays_workout"),
            InlineKeyboardButton("⚖️ Log Weight", callback_data="log_weight"),
        ],
        [
            InlineKeyboardButton("📊 My Progress", callback_data="my_progress"),
            InlineKeyboardButton("📋 Daily Plan", callback_data="daily_plan"),
        ],
        [
            InlineKeyboardButton("💪 Motivation", callback_data="motivation"),
            InlineKeyboardButton("⚙️ Settings", callback_data="settings"),
        ],
    ])


# ── Meal Type ──────────────────────────────────────────────────────────────────

def meal_type_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🌅 Breakfast", callback_data="meal_breakfast"),
            InlineKeyboardButton("☀️ Lunch", callback_data="meal_lunch"),
        ],
        [
            InlineKeyboardButton("🌙 Dinner", callback_data="meal_dinner"),
            InlineKeyboardButton("🍎 Snack", callback_data="meal_snack"),
        ],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel")],
    ])


# ── Water Quick Log ────────────────────────────────────────────────────────────

def water_quick_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🥛 250ml (1 glass)", callback_data="water_250"),
            InlineKeyboardButton("🍶 500ml (1 bottle)", callback_data="water_500"),
        ],
        [
            InlineKeyboardButton("💧 750ml", callback_data="water_750"),
            InlineKeyboardButton("🪣 1000ml (1L)", callback_data="water_1000"),
        ],
        [InlineKeyboardButton("✏️ Custom amount", callback_data="water_custom")],
    ])


# ── Workout Completion ─────────────────────────────────────────────────────────

def workout_done_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Completed!", callback_data="workout_done"),
            InlineKeyboardButton("⚡ Partial", callback_data="workout_partial"),
        ],
        [
            InlineKeyboardButton("😰 Skipped", callback_data="workout_skipped"),
            InlineKeyboardButton("🤕 Pain/Injury", callback_data="workout_pain"),
        ],
    ])


# ── Yes/No ─────────────────────────────────────────────────────────────────────

def yes_no_keyboard(yes_cb: str = "yes", no_cb: str = "no") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Yes", callback_data=yes_cb),
            InlineKeyboardButton("❌ No", callback_data=no_cb),
        ]
    ])


# ── Diet Preference ────────────────────────────────────────────────────────────

def diet_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🥩 Omnivore", callback_data="diet_omnivore"),
            InlineKeyboardButton("🥗 Vegetarian", callback_data="diet_vegetarian"),
        ],
        [
            InlineKeyboardButton("🌱 Vegan", callback_data="diet_vegan"),
            InlineKeyboardButton("🥑 Keto", callback_data="diet_keto"),
        ],
        [InlineKeyboardButton("🦴 Paleo", callback_data="diet_paleo")],
    ])


# ── Workout Level ──────────────────────────────────────────────────────────────

def workout_level_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🌱 Beginner (0-1 year)", callback_data="level_beginner")],
        [InlineKeyboardButton("💪 Intermediate (1-3 years)", callback_data="level_intermediate")],
        [InlineKeyboardButton("🔥 Advanced (3+ years)", callback_data="level_advanced")],
    ])


# ── Gym Days ───────────────────────────────────────────────────────────────────

def gym_days_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("2 days", callback_data="gym_2"),
            InlineKeyboardButton("3 days", callback_data="gym_3"),
            InlineKeyboardButton("4 days", callback_data="gym_4"),
        ],
        [
            InlineKeyboardButton("5 days", callback_data="gym_5"),
            InlineKeyboardButton("6 days", callback_data="gym_6"),
        ],
    ])


# ── Gender ─────────────────────────────────────────────────────────────────────

def gender_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👨 Male", callback_data="gender_male"),
            InlineKeyboardButton("👩 Female", callback_data="gender_female"),
        ]
    ])
