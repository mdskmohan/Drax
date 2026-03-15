"""
Motivation Agent — Claude Sonnet for rich motivational messages.
Claude excels at empathy and tone, making it ideal for this agent.
"""
import random
from app.agents.base_agent import BaseAgent
from app.models.user import User
from app.services.llm import llm
from app.services.youtube import search_exercise_video


MOTIVATION_ROLE = """You are an elite fitness motivation coach with the energy of a world-class personal trainer.
You know exactly the right words to inspire people to push through challenges.
You combine psychology, personal storytelling, and fitness science to motivate.
Your messages are energetic, personal, and always end with a clear call to action.
Never use generic platitudes — be specific, raw, and real. Make them feel like a champion."""

MOTIVATION_QUERIES = [
    "best fitness motivation workout",
    "weight loss transformation motivation",
    "gym motivation never give up",
    "morning workout motivation energy",
]


class MotivationAgent(BaseAgent):

    async def get_morning_motivation(self, user: User) -> str:
        weight_left = user.weight_to_lose_kg or 35
        return await llm.chat(
            messages=[{"role": "user", "content": f"Write a powerful morning motivation message. The user has {weight_left}kg left to lose. Make it personal, energetic, under 100 words. End with a bold power mantra on its own line."}],
            system=self._system_str(MOTIVATION_ROLE, user),
            temperature=0.9,
            max_tokens=200,
        )

    async def get_pre_workout_pump(self, user: User, workout_type: str) -> str:
        return await llm.chat(
            messages=[{"role": "user", "content": f"It's {workout_type} day! Write an intense 3-4 sentence pre-workout pump-up. Make them feel unstoppable right now."}],
            system=self._system_str(MOTIVATION_ROLE, user),
            temperature=0.95,
            max_tokens=150,
        )

    async def get_streak_celebration(self, user: User, streak_days: int) -> str:
        return await llm.fast(
            messages=[{"role": "user", "content": f"The user just hit {streak_days} days in a row! Write an exciting celebration message under 80 words."}],
            system=self._system_str(MOTIVATION_ROLE, user),
            temperature=0.9,
            max_tokens=150,
        )

    async def get_accountability_nudge(self, user: User, missed_item: str) -> str:
        return await llm.fast(
            messages=[{"role": "user", "content": f"The user missed: {missed_item} today. Write a compassionate but firm nudge (2-3 sentences). No shame — redirect and motivate for tomorrow."}],
            system=self._system_str(MOTIVATION_ROLE, user),
            temperature=0.7,
            max_tokens=150,
        )

    async def get_comeback_message(self, user: User, days_missed: int) -> str:
        return await llm.chat(
            messages=[{"role": "user", "content": f"User has been inactive for {days_missed} days. Welcome them back warmly, acknowledge the break, motivate to restart today. No judgment. Pure encouragement. Under 100 words."}],
            system=self._system_str(MOTIVATION_ROLE, user),
            temperature=0.8,
            max_tokens=200,
        )

    async def get_motivation_video(self) -> dict | None:
        videos = await search_exercise_video(random.choice(MOTIVATION_QUERIES), max_results=1)
        return videos[0] if videos else None

    def get_daily_quote(self) -> str:
        quotes = [
            "The body achieves what the mind believes.",
            "Every rep brings you closer to who you want to be.",
            "You didn't come this far to only come this far.",
            "Discipline is choosing between what you want now and what you want most.",
            "The pain you feel today is the strength you'll feel tomorrow.",
            "Fall in love with taking care of yourself.",
            "One workout at a time. One meal at a time. One day at a time.",
            "Be stronger than your excuses.",
        ]
        return random.choice(quotes)
