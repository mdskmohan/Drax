"""
Fitness Coach Agent — Claude Sonnet for workout generation.
"""
from app.agents.base_agent import BaseAgent
from app.models.user import User
from app.services import claude
from app.services.youtube import get_workout_videos


COACH_ROLE = """You are an expert personal fitness trainer and certified strength & conditioning coach.
Your job is to create safe, effective, progressive workout plans for weight loss and fitness improvement.
Always consider the user's current fitness level, available days, and long-term goals.
Workouts should combine cardio, strength training, and flexibility work appropriately.
Format workouts clearly with sets, reps, rest times, and technique tips.
Be encouraging, specific, and science-based."""


class FitnessCoachAgent(BaseAgent):

    async def generate_daily_workout(
        self,
        user: User,
        day_of_week: str,
        recent_workouts: list[dict] | None = None,
        is_gym_day: bool = True,
    ) -> dict:
        recent_summary = f"\nRecent workouts: {recent_workouts}" if recent_workouts else ""
        messages = [
            {
                "role": "user",
                "content": f"""Generate a complete {day_of_week} workout plan.
Is gym day: {is_gym_day}{recent_summary}

Return JSON with this exact structure:
{{
  "workout_type": "strength|cardio|hiit|yoga|rest",
  "duration_minutes": <number>,
  "warmup": [
    {{"exercise": "...", "duration_seconds": 60, "notes": "..."}}
  ],
  "main_workout": [
    {{
      "exercise": "...",
      "sets": 3,
      "reps": "10-12",
      "rest_seconds": 60,
      "muscle_group": "...",
      "notes": "..."
    }}
  ],
  "cooldown": [
    {{"exercise": "...", "duration_seconds": 60, "notes": "..."}}
  ],
  "calories_burned_estimate": <number>,
  "coach_tip": "...",
  "formatted_plan": "Full formatted workout plan text with emojis and clear sections"
}}""",
            }
        ]

        plan = await claude.json_completion(
            messages, system=self._system_str(COACH_ROLE, user), max_tokens=2048
        )

        exercise_names = [e.get("exercise", "") for e in plan.get("main_workout", [])]
        plan["youtube_links"] = await get_workout_videos(exercise_names[:5])
        return plan

    async def generate_rest_day_message(self, user: User) -> str:
        return await claude.chat_completion(
            messages=[{"role": "user", "content": "Today is a rest day. Write a short motivating message (3-4 sentences) explaining why rest is important and suggest 1-2 light recovery activities like a walk or stretching."}],
            system=self._system_str(COACH_ROLE, user),
            max_tokens=300,
        )

    async def adjust_workout_for_pain(self, user: User, pain_description: str) -> str:
        return await claude.chat_completion(
            messages=[{"role": "user", "content": f"The user reports: '{pain_description}'\n\nProvide a modified workout that avoids the affected area, suggest recovery steps, and advise when to see a doctor if needed. Be empathetic and safety-first."}],
            system=self._system_str(COACH_ROLE, user),
            max_tokens=600,
        )

    async def get_weekly_workout_schedule(self, user: User) -> dict:
        return await claude.json_completion(
            messages=[{"role": "user", "content": f"""Create a 7-day workout schedule. Gym days available: {user.gym_days_per_week}/week.
Return JSON: {{"schedule": {{"Monday": "...", "Tuesday": "...", "Wednesday": "...", "Thursday": "...", "Friday": "...", "Saturday": "...", "Sunday": "..."}}, "weekly_summary": "..."}}"""}],
            system=self._system_str(COACH_ROLE, user),
            max_tokens=600,
        )
