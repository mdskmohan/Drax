"""
Progress Agent — Claude Sonnet for detailed weekly reports and trend analysis.
"""
from app.agents.base_agent import BaseAgent
from app.models.user import User
from app.services.llm import llm


PROGRESS_ROLE = """You are a data-driven fitness progress analyst and coach.
You analyze trends, celebrate wins, identify patterns, and provide actionable insights.
You understand that weight loss is not linear — you help users interpret fluctuations wisely.
You combine statistical analysis with human understanding and empathy."""


class ProgressAgent(BaseAgent):

    async def generate_weekly_report(self, user: User, week_data: dict) -> str:
        stats = self._compute_week_stats(
            week_data.get("weight_logs", []),
            week_data.get("meal_logs", []),
            week_data.get("workout_logs", []),
            week_data.get("water_logs", []),
            user.daily_calorie_target or 2000,
            user.daily_water_target_ml or 3000,
        )
        return await llm.chat(
            messages=[{"role": "user", "content": f"""Generate a detailed weekly progress report.

WEEK STATS:
{self._format_stats(stats)}

Format with sections:
📊 THIS WEEK'S NUMBERS
🏆 WINS THIS WEEK
⚠️ AREAS TO IMPROVE
💡 RECOMMENDATIONS FOR NEXT WEEK
🎯 PROGRESS TOWARD GOAL

Make it personal, data-driven, and motivating. Use emojis."""}],
            system=self._system_str(PROGRESS_ROLE, user),
            max_tokens=1200,
        )

    async def analyze_weight_trend(self, user: User, weight_logs: list[dict]) -> dict:
        if len(weight_logs) < 2:
            return {"trend": "insufficient_data", "message": "Log weight for at least 2 weeks to see trends."}

        weights = [l["weight_kg"] for l in weight_logs]
        weeks = max(1, len(weight_logs))
        total_lost = weights[0] - weights[-1]
        weekly_rate = total_lost / weeks
        remaining = weights[-1] - (user.goal_weight_kg or weights[-1] - 35)
        eta_weeks = round(remaining / weekly_rate) if weekly_rate > 0 else None

        result = await llm.json(
            messages=[{"role": "user", "content": f"""Starting: {weights[0]}kg | Current: {weights[-1]}kg | Lost: {round(total_lost,2)}kg over {weeks} weeks | Rate: {round(weekly_rate,2)}kg/week | Remaining: {round(remaining,2)}kg
Return JSON: {{"trend": "on_track|ahead|behind|plateau", "analysis": "2-3 sentences", "eta_weeks": {eta_weeks or 0}}}"""}],
            system=self._system_str(PROGRESS_ROLE, user),
            fast=True,
            max_tokens=300,
        )
        result.update({"total_lost_kg": round(total_lost, 2), "weekly_rate_kg": round(weekly_rate, 2), "remaining_kg": round(remaining, 2)})
        return result

    async def log_weight_feedback(self, user: User, new_weight: float) -> str:
        change = (user.current_weight_kg or new_weight) - new_weight
        direction = f"lost {abs(round(change, 2))}kg" if change > 0 else f"gained {abs(round(change, 2))}kg" if change < 0 else "no change"
        return await llm.fast(
            messages=[{"role": "user", "content": f"User logged {new_weight}kg (previous: {user.current_weight_kg}kg, change: {direction}). Write a 2-sentence response. Celebrate loss, normalize gain, explain plateau."}],
            system=self._system_str(PROGRESS_ROLE, user),
            max_tokens=150,
        )

    def build_progress_bar(self, current_kg: float, start_kg: float, goal_kg: float) -> str:
        total = start_kg - goal_kg
        lost = start_kg - current_kg
        pct = min(lost / total, 1.0) if total > 0 else 0
        filled = int(pct * 20)
        bar = "█" * filled + "░" * (20 - filled)
        return f"[{bar}] {round(pct*100)}%\nLost: {round(lost,1)}kg / {round(total,1)}kg | Remaining: {round(total-lost,1)}kg"

    def _compute_week_stats(self, weight_logs, meal_logs, workout_logs, water_logs, calorie_target, water_target):
        avg_cal = sum(m.get("calories", 0) for m in meal_logs) / len(meal_logs) if meal_logs else 0
        avg_water = sum(w.get("amount_ml", 0) for w in water_logs) / 7
        completed = sum(1 for w in workout_logs if w.get("completed"))
        weight_change = (weight_logs[-1].get("weight_kg", 0) - weight_logs[0].get("weight_kg", 0)) if len(weight_logs) >= 2 else None
        return {
            "avg_daily_calories": round(avg_cal),
            "calorie_target": calorie_target,
            "calorie_adherence_pct": round(avg_cal / calorie_target * 100) if calorie_target else 0,
            "workouts_completed": completed,
            "workouts_total": len(workout_logs),
            "avg_daily_water_ml": round(avg_water),
            "water_target_ml": water_target,
            "weight_change_kg": round(weight_change, 2) if weight_change is not None else "not logged",
            "meals_logged": len(meal_logs),
        }

    def _format_stats(self, stats: dict) -> str:
        return "\n".join(f"  {k}: {v}" for k, v in stats.items())
