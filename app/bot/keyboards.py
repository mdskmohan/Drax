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
            InlineKeyboardButton("⚙️ Equipment", callback_data="equipment"),
        ],
        [
            InlineKeyboardButton("📱 Health Sync", callback_data="sync"),
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


# ── Language Selection ─────────────────────────────────────────────────────────

def language_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"),
            InlineKeyboardButton("🇮🇳 Hindi", callback_data="lang_hi"),
        ],
        [
            InlineKeyboardButton("🇪🇸 Spanish", callback_data="lang_es"),
            InlineKeyboardButton("🇫🇷 French", callback_data="lang_fr"),
        ],
        [
            InlineKeyboardButton("🇦🇪 Arabic", callback_data="lang_ar"),
            InlineKeyboardButton("🇩🇪 German", callback_data="lang_de"),
        ],
        [InlineKeyboardButton("🌐 Other (English)", callback_data="lang_en")],
    ])


# ── Equipment Setup Type ───────────────────────────────────────────────────────

def equipment_setup_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏋️ Full Gym (machines + free weights)", callback_data="equip_setup_gym")],
        [InlineKeyboardButton("🏠 Home Gym (limited equipment)", callback_data="equip_setup_home")],
        [InlineKeyboardButton("💪 Bodyweight Only (no equipment)", callback_data="equip_setup_bodyweight")],
        [InlineKeyboardButton("📷 Send Photo of Your Equipment", callback_data="equip_setup_photo")],
    ])


# ── Equipment Selection (home/gym specific items) ─────────────────────────────

def equipment_selection_keyboard(selected: list[str]) -> InlineKeyboardMarkup:
    """Multi-select equipment keyboard. Selected items show a checkmark."""
    all_equipment = [
        ("🏋️ Barbell", "barbell"),
        ("💪 Dumbbells", "dumbbells"),
        ("⚙️ Cable Machine", "cable machine"),
        ("🦾 Smith Machine", "smith machine"),
        ("🔩 Resistance Bands", "resistance bands"),
        ("⚽ Kettlebells", "kettlebells"),
        ("🏊 Pull-up Bar", "pull-up bar"),
        ("🪑 Bench", "bench"),
        ("🔄 Lat Pulldown", "lat pulldown"),
        ("🦵 Leg Press", "leg press"),
        ("🏃 Treadmill", "treadmill"),
        ("🚴 Stationary Bike", "stationary bike"),
    ]
    rows = []
    for i in range(0, len(all_equipment), 2):
        row = []
        for label, key in all_equipment[i:i+2]:
            is_selected = key in selected
            btn_label = f"✅ {label}" if is_selected else label
            row.append(InlineKeyboardButton(btn_label, callback_data=f"equip_toggle_{key}"))
        rows.append(row)
    rows.append([InlineKeyboardButton("✅ Done — Save Equipment", callback_data="equip_done")])
    return InlineKeyboardMarkup(rows)


# ── Gym Schedule (day selection) ───────────────────────────────────────────────

def gym_schedule_keyboard(selected_days: list[str]) -> InlineKeyboardMarkup:
    """Multi-select day keyboard for gym schedule."""
    days = [
        ("Mon", "Monday"), ("Tue", "Tuesday"), ("Wed", "Wednesday"),
        ("Thu", "Thursday"), ("Fri", "Friday"), ("Sat", "Saturday"), ("Sun", "Sunday"),
    ]
    row1 = []
    row2 = []
    for i, (short, full) in enumerate(days):
        is_selected = full in selected_days
        label = f"✅{short}" if is_selected else short
        btn = InlineKeyboardButton(label, callback_data=f"schedule_{full}")
        if i < 4:
            row1.append(btn)
        else:
            row2.append(btn)
    return InlineKeyboardMarkup([
        row1, row2,
        [InlineKeyboardButton("✅ Done — Save Schedule", callback_data="schedule_done")],
    ])


# ── Health Sync ────────────────────────────────────────────────────────────────

def health_sync_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📱 Apple Health Setup Guide", callback_data="sync_apple")],
        [InlineKeyboardButton("🤖 Android Health Connect Guide", callback_data="sync_android")],
        [InlineKeyboardButton("🔗 My Sync URL & Token", callback_data="sync_token")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel")],
    ])


# ── Notification Settings ──────────────────────────────────────────────────────

_NOTIF_META = {
    "morning_plan":    ("🌅", "Morning Plan"),
    "preworkout":      ("⚡", "Pre-Workout"),
    "evening_checkin": ("🌙", "Evening Check-in"),
    "water_reminder":  ("💧", "Water Reminders"),
    "weekly_report":   ("📊", "Weekly Report"),
}


def _notif_status(pref: dict) -> str:
    return "✅" if pref.get("enabled", True) else "❌"


def _days_summary(days: list) -> str:
    short = {"Monday": "Mon", "Tuesday": "Tue", "Wednesday": "Wed",
             "Thursday": "Thu", "Friday": "Fri", "Saturday": "Sat", "Sunday": "Sun"}
    if not days:
        return "none"
    if len(days) == 7:
        return "Every day"
    return " ".join(short.get(d, d[:3]) for d in days)


def notification_menu_keyboard(user) -> InlineKeyboardMarkup:
    """Main notification settings menu — one button per notification type."""
    from app.models.user import DEFAULT_NOTIFICATION_PREFS
    rows = []
    for notif_type, (emoji, label) in _NOTIF_META.items():
        pref = user.get_notification_pref(notif_type)
        status = _notif_status(pref)
        if notif_type == "water_reminder":
            detail = f"{pref.get('start_hour', 8):02d}:00–{pref.get('end_hour', 20):02d}:00 · {pref.get('interval_hours', 2)}h"
        elif notif_type == "weekly_report":
            detail = f"{pref.get('day', 'Sunday')[:3]} {pref.get('time', '08:00')}"
        else:
            days = _days_summary(pref.get("days", []))
            detail = f"{pref.get('time', '?')} · {days}"
        rows.append([InlineKeyboardButton(
            f"{status} {emoji} {label}  —  {detail}",
            callback_data=f"notif_view_{notif_type}",
        )])

    # All-on / all-off toggle
    any_enabled = any(
        user.get_notification_pref(t).get("enabled", True) for t in _NOTIF_META
    )
    toggle_label = "🔇 Pause All Notifications" if any_enabled else "🔔 Resume All Notifications"
    toggle_cb = "notif_pauseall" if any_enabled else "notif_resumeall"
    rows.append([InlineKeyboardButton(toggle_label, callback_data=toggle_cb)])
    rows.append([InlineKeyboardButton("← Back to Menu", callback_data="cancel")])
    return InlineKeyboardMarkup(rows)


def notification_type_keyboard(user, notif_type: str) -> InlineKeyboardMarkup:
    """Settings panel for one notification type."""
    pref = user.get_notification_pref(notif_type)
    is_enabled = pref.get("enabled", True)
    toggle_label = "⏸ Disable" if is_enabled else "▶️ Enable"

    rows = []
    if notif_type == "water_reminder":
        rows.append([InlineKeyboardButton(toggle_label, callback_data=f"notif_toggle_{notif_type}")])
        rows.append([
            InlineKeyboardButton("⏰ Start Hour", callback_data=f"notif_settime_{notif_type}_start"),
            InlineKeyboardButton("⏰ End Hour", callback_data=f"notif_settime_{notif_type}_end"),
        ])
        rows.append([
            InlineKeyboardButton(
                f"{'✅ ' if pref.get('interval_hours') == h else ''}Every {h}h",
                callback_data=f"notif_interval_{h}",
            )
            for h in [1, 2, 3, 4]
        ])
    elif notif_type == "weekly_report":
        rows.append([InlineKeyboardButton(toggle_label, callback_data=f"notif_toggle_{notif_type}")])
        rows.append([
            InlineKeyboardButton("⏰ Change Time", callback_data=f"notif_settime_{notif_type}"),
            InlineKeyboardButton("📅 Change Day", callback_data=f"notif_setdays_{notif_type}"),
        ])
    else:
        rows.append([InlineKeyboardButton(toggle_label, callback_data=f"notif_toggle_{notif_type}")])
        rows.append([
            InlineKeyboardButton("⏰ Change Time", callback_data=f"notif_settime_{notif_type}"),
            InlineKeyboardButton("📅 Change Days", callback_data=f"notif_setdays_{notif_type}"),
        ])
    rows.append([InlineKeyboardButton("← Back", callback_data="notif_menu")])
    return InlineKeyboardMarkup(rows)


def notification_days_keyboard(selected_days: list, notif_type: str) -> InlineKeyboardMarkup:
    """Multi-select day keyboard for notification day configuration."""
    days = [("Mon", "Monday"), ("Tue", "Tuesday"), ("Wed", "Wednesday"),
            ("Thu", "Thursday"), ("Fri", "Friday"), ("Sat", "Saturday"), ("Sun", "Sunday")]
    row1, row2 = [], []
    for i, (short, full) in enumerate(days):
        label = f"✅{short}" if full in selected_days else short
        btn = InlineKeyboardButton(label, callback_data=f"notif_day_{notif_type}_{full}")
        (row1 if i < 4 else row2).append(btn)
    return InlineKeyboardMarkup([
        row1, row2,
        [InlineKeyboardButton("✅ Save Days", callback_data=f"notif_daydone_{notif_type}")],
        [InlineKeyboardButton("← Back", callback_data=f"notif_view_{notif_type}")],
    ])


def notification_weekday_keyboard(current_day: str, notif_type: str) -> InlineKeyboardMarkup:
    """Single-select day keyboard for weekly report day."""
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    rows = []
    for day in days:
        label = f"✅ {day}" if day == current_day else day
        rows.append([InlineKeyboardButton(label, callback_data=f"notif_weekday_{notif_type}_{day}")])
    rows.append([InlineKeyboardButton("← Back", callback_data=f"notif_view_{notif_type}")])
    return InlineKeyboardMarkup(rows)


def notification_hour_keyboard(notif_type: str, subtype: str = "") -> InlineKeyboardMarkup:
    """Hour picker (0–23) for water reminder start/end hours."""
    suffix = f"_{subtype}" if subtype else ""
    rows = []
    for start_h in range(0, 24, 6):
        row = [
            InlineKeyboardButton(f"{h:02d}:00", callback_data=f"notif_hour_{notif_type}{suffix}_{h}")
            for h in range(start_h, min(start_h + 6, 24))
        ]
        rows.append(row)
    rows.append([InlineKeyboardButton("← Back", callback_data=f"notif_view_{notif_type}")])
    return InlineKeyboardMarkup(rows)


# ── Gender ─────────────────────────────────────────────────────────────────────

def gender_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👨 Male", callback_data="gender_male"),
            InlineKeyboardButton("👩 Female", callback_data="gender_female"),
        ]
    ])
