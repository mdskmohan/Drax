"""
Base agent with shared context-building utilities.
All agents inherit from this.
"""
from app.models.user import User


_LANGUAGE_NAMES = {
    "hi": "Hindi",
    "es": "Spanish",
    "fr": "French",
    "ar": "Arabic",
    "de": "German",
}


class BaseAgent:
    def _system_str(self, role: str, user: User) -> str:
        """Return a combined system prompt string for Claude's system= parameter."""
        base = f"{role}\n\nUSER PROFILE:\n{self._user_context(user)}"
        lang = getattr(user, "language", "en") or "en"
        if lang != "en" and lang in _LANGUAGE_NAMES:
            lang_name = _LANGUAGE_NAMES[lang]
            base += f"\n\nIMPORTANT: Respond in {lang_name} language."
        return base

    def _user_context(self, user: User) -> str:
        """Build a standard user profile context string for prompts."""
        lines = [
            f"User: {user.full_name or user.first_name or 'User'}",
            f"Age: {user.age or 'unknown'}",
            f"Gender: {user.gender or 'unknown'}",
            f"Height: {user.height_cm or 'unknown'} cm",
            f"Current weight: {user.current_weight_kg or 'unknown'} kg",
            f"Goal weight: {user.goal_weight_kg or 'unknown'} kg",
            f"Weight to lose: {user.weight_to_lose_kg or 'unknown'} kg",
            f"Timeline: {user.timeline_months or 10} months",
            f"Diet preference: {user.diet_preference.value if user.diet_preference else 'omnivore'}",
            f"Workout level: {user.workout_level.value if user.workout_level else 'beginner'}",
            f"Gym days/week: {user.gym_days_per_week or 3}",
            f"Daily calorie target: {user.daily_calorie_target or 'TBD'} kcal",
            f"Daily water target: {user.daily_water_target_ml or 3000} ml",
        ]
        if user.tdee:
            lines.append(f"TDEE: {round(user.tdee)} kcal")

        # ── Long-term adaptation profile ─────────────────────────────────────
        # This is what Drax has learned about this specific person over weeks.
        # It is updated every Sunday by the AdaptationAgent and injected into
        # every LLM call so all decisions — workout, meals, motivation — are
        # shaped by real, accumulated evidence rather than generic heuristics.
        profile = getattr(user, "adaptation_profile", None) or {}
        if profile:
            meso_week = profile.get("mesocycle_week", 1)
            deload_flag = " — DELOAD WEEK: 50% volume, light weights, focus on form" if meso_week == 4 else ""
            lines += [
                "",
                "=== DRAX ADAPTATION PROFILE (learned from weeks of real data) ===",
                f"Training phase: {profile.get('training_phase', 'cutting')}",
                f"Mesocycle week: {meso_week}/4{deload_flag}",
                f"Avg weekly weight change: {profile.get('avg_weekly_weight_change_kg', 0):+.2f} kg/week",
                f"4-week calorie adherence: {profile.get('avg_calorie_adherence_pct', 0)}% of days on target",
                f"4-week protein adherence: {profile.get('avg_protein_adherence_pct', 0)}% of daily target",
                f"4-week workout completion: {int(profile.get('avg_workout_completion_rate', 1.0) * 100)}%",
                f"Intensity recommendation: {profile.get('intensity_recommendation', 'moderate')}",
            ]

            skip = profile.get("skip_patterns", {})
            if skip:
                skip_str = ", ".join(f"{d} ({c}x in 4 weeks)" for d, c in skip.items())
                lines.append(
                    f"CONSISTENT SKIP DAYS: {skip_str} — "
                    "do NOT programme heavy sessions on these days; place rest or light work here"
                )

            pain = profile.get("chronic_pain_areas", [])
            if pain:
                lines.append(
                    f"CHRONIC PAIN/INJURY HISTORY: {'; '.join(pain[-3:])} — "
                    "avoid exercises that directly stress these areas"
                )

            if profile.get("recommended_split"):
                lines.append(f"Recommended training split: {profile['recommended_split']}")

            focus = profile.get("key_focus_areas", [])
            if focus:
                lines.append(f"Key focus areas this block: {', '.join(focus)}")

            if profile.get("coach_observations"):
                lines.append(f"Coach observations: {profile['coach_observations']}")

            lines.append("=== END ADAPTATION PROFILE ===")

        return "\n".join(lines)

    def _system_prompt(self, role: str, context: str) -> dict:
        return {"role": "system", "content": f"{role}\n\nUSER PROFILE:\n{context}"}
