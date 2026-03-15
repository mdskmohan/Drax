"""
Fitness Coach Agent — Claude Sonnet for workout generation, with daily caching.
"""
from datetime import date
from app.agents.base_agent import BaseAgent
from app.models.user import User
from app.services.llm import llm
from app.services.youtube import get_workout_videos

# Simple in-process daily cache: {(user_id, date, day_of_week) -> plan}
_workout_cache: dict = {}


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
        # Return cached plan if already generated today (saves LLM cost on repeat /workout calls)
        cache_key = (user.id, date.today(), day_of_week)
        if cache_key in _workout_cache:
            return _workout_cache[cache_key]

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

        plan = await llm.json(
            messages, system=self._system_str(COACH_ROLE, user), max_tokens=2048
        )

        exercise_names = [e.get("exercise", "") for e in plan.get("main_workout", [])]
        plan["youtube_links"] = await get_workout_videos(exercise_names[:5])

        _workout_cache[cache_key] = plan
        return plan

    def generate_rest_day_message(self, user: User) -> str:
        """Return a rest-day message from pre-written variations — no LLM needed."""
        import random
        name = user.first_name or "Champion"
        messages = [
            f"Rest day, {name}! Your muscles repair and grow stronger during recovery — this is where the transformation happens. Go for a 20-min walk, stretch for 10 minutes, and sleep 8 hours. Tomorrow you'll be stronger. 💪",
            f"Today is your secret weapon, {name}. Elite athletes treat rest days as seriously as training days. Light walking, foam rolling, and good nutrition today = a beast in the gym tomorrow. Trust the process.",
            f"Recovery day! Your body is rebuilding right now, {name}. Skip the guilt — you've earned this. Try a 15-minute stretch routine or a gentle walk. Fuel up with protein and hydrate well. Come back tomorrow ready to crush it.",
            f"Rest is not weakness, {name} — it's strategy. Your muscles are synthesizing protein and adapting. Keep moving lightly (walk, yoga), eat clean, drink your water, and let the gains happen.",
        ]
        return random.choice(messages)

    async def adjust_workout_for_pain(self, user: User, pain_description: str) -> str:
        return await llm.chat(
            messages=[{"role": "user", "content": f"The user reports: '{pain_description}'\n\nProvide a modified workout that avoids the affected area, suggest recovery steps, and advise when to see a doctor if needed. Be empathetic and safety-first."}],
            system=self._system_str(COACH_ROLE, user),
            max_tokens=600,
        )

    async def get_weekly_workout_schedule(self, user: User) -> dict:
        return await llm.json(
            messages=[{"role": "user", "content": f"""Create a 7-day workout schedule. Gym days available: {user.gym_days_per_week}/week.
Return JSON: {{"schedule": {{"Monday": "...", "Tuesday": "...", "Wednesday": "...", "Thursday": "...", "Friday": "...", "Saturday": "...", "Sunday": "..."}}, "weekly_summary": "..."}}"""}],
            system=self._system_str(COACH_ROLE, user),
            max_tokens=600,
        )
