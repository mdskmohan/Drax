"""
Recovery Agent — Claude Sonnet for injury assessment and modified workouts.
Claude's strong safety awareness makes it ideal for health-sensitive advice.
"""
from app.agents.base_agent import BaseAgent
from app.models.user import User
from app.services import claude


RECOVERY_ROLE = """You are a sports medicine expert, physical therapist, and recovery specialist.
You help athletes manage pain, prevent injury, and recover effectively.
You always prioritize safety and refer to medical professionals when appropriate.
You provide evidence-based recovery protocols and workout modifications.
Never diagnose medical conditions — always recommend seeing a doctor for serious issues."""


class RecoveryAgent(BaseAgent):

    async def assess_pain(self, user: User, pain_description: str) -> dict:
        return await claude.json_completion(
            messages=[{"role": "user", "content": f"""User reports: "{pain_description}"

Return JSON:
{{
  "severity": "mild|moderate|severe",
  "affected_area": "...",
  "see_doctor": true/false,
  "rest_days_recommended": 0,
  "safe_exercises": ["..."],
  "exercises_to_avoid": ["..."],
  "recovery_tips": ["..."],
  "recommendation": "2-3 sentences",
  "emergency_note": null
}}"""}],
            system=self._system_str(RECOVERY_ROLE, user),
            max_tokens=600,
        )

    async def generate_modified_workout(self, user: User, pain_assessment: dict) -> str:
        affected = pain_assessment.get("affected_area", "unknown")
        safe = pain_assessment.get("safe_exercises", [])
        avoid = pain_assessment.get("exercises_to_avoid", [])
        return await claude.chat_completion(
            messages=[{"role": "user", "content": f"Create a modified 30-45 min workout avoiding the {affected} area.\nSafe exercises: {safe}\nAvoid: {avoid}\nInclude sets/reps/rest and technique notes."}],
            system=self._system_str(RECOVERY_ROLE, user),
            max_tokens=800,
        )

    async def get_recovery_protocol(self, user: User, injury_type: str) -> str:
        return await claude.chat_completion(
            messages=[{"role": "user", "content": f"Provide a 5-7 day recovery protocol for: {injury_type}\nInclude day-by-day plan, RICE protocol if applicable, stretches, return-to-training timeline, warning signs."}],
            system=self._system_str(RECOVERY_ROLE, user),
            max_tokens=800,
        )

    async def check_overtraining(self, user: User, workout_frequency: dict) -> str:
        return await claude.fast_completion(
            messages=[{"role": "user", "content": f"Analyze potential overtraining:\n{workout_frequency}\nAssess and give recommendations in under 150 words."}],
            system=self._system_str(RECOVERY_ROLE, user),
            max_tokens=200,
        )
