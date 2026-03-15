"""
Base agent with shared context-building utilities.
All agents inherit from this.
"""
from app.models.user import User


class BaseAgent:
    def _system_str(self, role: str, user: User) -> str:
        """Return a combined system prompt string for Claude's system= parameter."""
        return f"{role}\n\nUSER PROFILE:\n{self._user_context(user)}"

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
        return "\n".join(lines)

    def _system_prompt(self, role: str, context: str) -> dict:
        return {"role": "system", "content": f"{role}\n\nUSER PROFILE:\n{context}"}
