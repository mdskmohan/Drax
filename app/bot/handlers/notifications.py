"""
Notification settings handler.
Allows users to configure time, days, and enable/disable for each notification type.
"""
import re
from telegram import Update
from telegram.ext import ContextTypes
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.user import User
from app.bot.keyboards import (
    notification_menu_keyboard,
    notification_type_keyboard,
    notification_days_keyboard,
    notification_weekday_keyboard,
    notification_hour_keyboard,
    _NOTIF_META,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _format_notif_detail(user, notif_type: str) -> str:
    """Build a human-readable summary of one notification's settings."""
    pref = user.get_notification_pref(notif_type)
    emoji, label = _NOTIF_META[notif_type]
    status = "✅ Enabled" if pref.get("enabled", True) else "❌ Disabled"

    if notif_type == "water_reminder":
        return (
            f"{emoji} *{label}*\n\n"
            f"Status: {status}\n"
            f"Active hours: {pref.get('start_hour', 8):02d}:00 – {pref.get('end_hour', 20):02d}:00\n"
            f"Reminder every: *{pref.get('interval_hours', 2)} hours*"
        )
    elif notif_type == "weekly_report":
        return (
            f"{emoji} *{label}*\n\n"
            f"Status: {status}\n"
            f"Day: *{pref.get('day', 'Sunday')}*\n"
            f"Time: *{pref.get('time', '08:00')}*  (your local time)"
        )
    else:
        from app.bot.keyboards import _days_summary
        days = _days_summary(pref.get("days", []))
        return (
            f"{emoji} *{label}*\n\n"
            f"Status: {status}\n"
            f"Time: *{pref.get('time', '?')}*  (your local time)\n"
            f"Days: *{days}*"
        )


def _parse_time(text: str) -> str | None:
    """Validate and normalise a HH:MM time string. Returns None if invalid."""
    text = text.strip().replace(".", ":").replace(",", ":").replace(" ", ":")
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", text)
    if not m:
        return None
    h, mins = int(m.group(1)), int(m.group(2))
    if not (0 <= h <= 23 and 0 <= mins <= 59):
        return None
    return f"{h:02d}:{mins:02d}"


# ── Main command ───────────────────────────────────────────────────────────────

async def notifications_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Show the notification settings menu.
    Works from both /notifications command (message) and the Settings button (callback).
    """
    user_id = update.effective_user.id
    query = update.callback_query

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            if query:
                await query.answer("Please /start first.", show_alert=True)
            else:
                await update.message.reply_text("Please /start first.")
            return

    msg = (
        "🔔 *Notification Settings*\n\n"
        "Tap any notification to change its time, days, or toggle it on/off.\n"
        "All times are in *your local timezone* "
        f"(`{user.timezone or 'Asia/Kolkata'}`)."
    )
    kwargs = {"parse_mode": "Markdown", "reply_markup": notification_menu_keyboard(user)}
    if query:
        await query.answer()
        await query.edit_message_text(msg, **kwargs)
    else:
        await update.message.reply_text(msg, **kwargs)


# ── Callback handler ───────────────────────────────────────────────────────────

async def handle_notification_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Handle all notif_* callbacks. Returns True if handled, False if not ours.
    """
    query = update.callback_query
    data = query.data

    if not data.startswith("notif_"):
        return False

    await query.answer()
    user_id = query.from_user.id

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            return False

        # ── Main menu ──────────────────────────────────────────────────────
        if data == "notif_menu":
            text = (
                "🔔 *Notification Settings*\n\n"
                "Tap a notification to configure it.\n"
                f"Timezone: `{user.timezone or 'Asia/Kolkata'}`"
            )
            await query.edit_message_text(
                text, parse_mode="Markdown",
                reply_markup=notification_menu_keyboard(user),
            )
            return True

        # ── View one notification type ─────────────────────────────────────
        if data.startswith("notif_view_"):
            notif_type = data.replace("notif_view_", "")
            if notif_type not in _NOTIF_META:
                return False
            text = _format_notif_detail(user, notif_type)
            await query.edit_message_text(
                text, parse_mode="Markdown",
                reply_markup=notification_type_keyboard(user, notif_type),
            )
            return True

        # ── Toggle enable/disable ──────────────────────────────────────────
        if data.startswith("notif_toggle_"):
            notif_type = data.replace("notif_toggle_", "")
            if notif_type not in _NOTIF_META:
                return False
            pref = user.get_notification_pref(notif_type)
            user.set_notification_pref(notif_type, {"enabled": not pref.get("enabled", True)})
            await session.commit()
            text = _format_notif_detail(user, notif_type)
            await query.edit_message_text(
                text, parse_mode="Markdown",
                reply_markup=notification_type_keyboard(user, notif_type),
            )
            return True

        # ── Pause / resume all ─────────────────────────────────────────────
        if data in ("notif_pauseall", "notif_resumeall"):
            enabled = (data == "notif_resumeall")
            for notif_type in _NOTIF_META:
                user.set_notification_pref(notif_type, {"enabled": enabled})
            await session.commit()
            status_text = "resumed ✅" if enabled else "paused ⏸"
            text = (
                f"🔔 *Notification Settings*\n\n"
                f"All notifications {status_text}.\n\n"
                f"Timezone: `{user.timezone or 'Asia/Kolkata'}`"
            )
            await query.edit_message_text(
                text, parse_mode="Markdown",
                reply_markup=notification_menu_keyboard(user),
            )
            return True

        # ── Prompt to type a time ──────────────────────────────────────────
        if data.startswith("notif_settime_"):
            remainder = data.replace("notif_settime_", "")
            # water_reminder_start / water_reminder_end vs just notif_type
            if remainder.endswith("_start"):
                notif_type = remainder[:-6]
                subtype = "start"
            elif remainder.endswith("_end"):
                notif_type = remainder[:-4]
                subtype = "end"
            else:
                notif_type = remainder
                subtype = None

            if notif_type not in _NOTIF_META:
                return False

            context.user_data["awaiting_notif_time"] = notif_type
            context.user_data["awaiting_notif_subtype"] = subtype

            if subtype == "start":
                prompt = "Type the *start hour* for water reminders (e.g., `07:00` or `8:00`):"
            elif subtype == "end":
                prompt = "Type the *end hour* for water reminders (e.g., `21:00`):"
            else:
                _, label = _NOTIF_META[notif_type]
                prompt = f"Type the time for *{label}* (e.g., `06:30`):\n_Format: HH:MM (24-hour)_"

            await query.edit_message_text(prompt, parse_mode="Markdown")
            return True

        # ── Show day-picker keyboard ───────────────────────────────────────
        if data.startswith("notif_setdays_"):
            notif_type = data.replace("notif_setdays_", "")
            if notif_type not in _NOTIF_META:
                return False

            if notif_type == "weekly_report":
                pref = user.get_notification_pref(notif_type)
                await query.edit_message_text(
                    "📅 Which day should the weekly report be sent?",
                    reply_markup=notification_weekday_keyboard(pref.get("day", "Sunday"), notif_type),
                )
            else:
                pref = user.get_notification_pref(notif_type)
                selected = pref.get("days", list(_NOTIF_META.keys()))
                context.user_data[f"notif_days_{notif_type}"] = list(selected)
                _, label = _NOTIF_META[notif_type]
                await query.edit_message_text(
                    f"📅 *{label}* — which days should this be sent?\nTap to toggle:",
                    parse_mode="Markdown",
                    reply_markup=notification_days_keyboard(selected, notif_type),
                )
            return True

        # ── Toggle a day in the day-picker ────────────────────────────────
        if data.startswith("notif_day_"):
            # notif_day_{notif_type}_{DayName}
            remainder = data.replace("notif_day_", "")
            # Find the notif_type (could contain _) by matching known types
            notif_type = None
            day_name = None
            for t in _NOTIF_META:
                if remainder.startswith(t + "_"):
                    notif_type = t
                    day_name = remainder[len(t) + 1:]
                    break
            if not notif_type or not day_name:
                return False

            key = f"notif_days_{notif_type}"
            selected = context.user_data.get(key, user.get_notification_pref(notif_type).get("days", []))
            if day_name in selected:
                selected.remove(day_name)
            else:
                selected.append(day_name)
            context.user_data[key] = selected

            # Re-order days canonically
            day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            selected = [d for d in day_order if d in selected]
            context.user_data[key] = selected

            _, label = _NOTIF_META[notif_type]
            from app.bot.keyboards import _days_summary
            await query.edit_message_text(
                f"📅 *{label}* — tap to toggle:\nSelected: *{_days_summary(selected)}*",
                parse_mode="Markdown",
                reply_markup=notification_days_keyboard(selected, notif_type),
            )
            return True

        # ── Save days ──────────────────────────────────────────────────────
        if data.startswith("notif_daydone_"):
            notif_type = data.replace("notif_daydone_", "")
            if notif_type not in _NOTIF_META:
                return False
            selected = context.user_data.pop(f"notif_days_{notif_type}", [])
            if not selected:
                await query.answer("Select at least one day!", show_alert=True)
                return True
            user.set_notification_pref(notif_type, {"days": selected})
            await session.commit()
            text = _format_notif_detail(user, notif_type)
            await query.edit_message_text(
                text, parse_mode="Markdown",
                reply_markup=notification_type_keyboard(user, notif_type),
            )
            return True

        # ── Set weekly report day ──────────────────────────────────────────
        if data.startswith("notif_weekday_"):
            remainder = data.replace("notif_weekday_", "")
            notif_type = None
            day_name = None
            for t in _NOTIF_META:
                if remainder.startswith(t + "_"):
                    notif_type = t
                    day_name = remainder[len(t) + 1:]
                    break
            if not notif_type or not day_name:
                return False
            user.set_notification_pref(notif_type, {"day": day_name})
            await session.commit()
            text = _format_notif_detail(user, notif_type)
            await query.edit_message_text(
                text, parse_mode="Markdown",
                reply_markup=notification_type_keyboard(user, notif_type),
            )
            return True

        # ── Set water reminder interval ────────────────────────────────────
        if data.startswith("notif_interval_"):
            try:
                hours = int(data.replace("notif_interval_", ""))
            except ValueError:
                return False
            user.set_notification_pref("water_reminder", {"interval_hours": hours})
            await session.commit()
            text = _format_notif_detail(user, "water_reminder")
            await query.edit_message_text(
                text, parse_mode="Markdown",
                reply_markup=notification_type_keyboard(user, "water_reminder"),
            )
            return True

        # ── Set water hour via hour-picker (notif_hour_{type}_{start|end}_{hour}) ──
        if data.startswith("notif_hour_"):
            parts = data.split("_")
            # notif_hour_{notif_type}_{start|end}_{hour}
            # e.g. notif_hour_water_reminder_start_8 → parts = [notif, hour, water, reminder, start, 8]
            try:
                hour = int(parts[-1])
                subtype = parts[-2]    # start or end
                notif_type = "_".join(parts[2:-2])
            except (ValueError, IndexError):
                return False
            if notif_type not in _NOTIF_META:
                return False
            key = "start_hour" if subtype == "start" else "end_hour"
            user.set_notification_pref(notif_type, {key: hour})
            await session.commit()
            text = _format_notif_detail(user, notif_type)
            await query.edit_message_text(
                text, parse_mode="Markdown",
                reply_markup=notification_type_keyboard(user, notif_type),
            )
            return True

    return False


async def process_notif_time_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Handle text input when user is typing a time for a notification.
    Returns True if we consumed the message.
    """
    notif_type = context.user_data.get("awaiting_notif_time")
    if not notif_type:
        return False

    subtype = context.user_data.pop("awaiting_notif_subtype", None)
    context.user_data.pop("awaiting_notif_time", None)

    text = update.message.text.strip()
    parsed = _parse_time(text)
    if not parsed:
        await update.message.reply_text(
            "Invalid time format. Please use HH:MM (e.g., `06:30` or `21:00`).\n"
            "Use /notifications to try again.",
            parse_mode="Markdown",
        )
        return True

    user_id = update.effective_user.id
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            return True

        h, m = map(int, parsed.split(":"))

        if subtype == "start":
            user.set_notification_pref(notif_type, {"start_hour": h})
            saved_label = f"start hour to {parsed}"
        elif subtype == "end":
            user.set_notification_pref(notif_type, {"end_hour": h})
            saved_label = f"end hour to {parsed}"
        else:
            user.set_notification_pref(notif_type, {"time": parsed})
            saved_label = f"time to {parsed}"

        await session.commit()

        _, label = _NOTIF_META.get(notif_type, ("🔔", notif_type))
        await update.message.reply_text(
            f"✅ *{label}* {saved_label} saved!\n\n"
            f"{_format_notif_detail(user, notif_type)}",
            parse_mode="Markdown",
            reply_markup=notification_type_keyboard(user, notif_type),
        )

    return True
