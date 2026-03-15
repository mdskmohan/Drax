"""
Hydration Agent — rule-based tracking with Claude Haiku for tips.
"""
from app.agents.base_agent import BaseAgent
from app.models.user import User
from app.services import claude


class HydrationAgent(BaseAgent):

    def calculate_daily_target(self, user: User, is_workout_day: bool = False) -> int:
        base_ml = int((user.current_weight_kg or 80) * 35)
        workout_bonus = 500 if is_workout_day else 0
        return max(2000, min(base_ml + workout_bonus, 5000))

    def get_hydration_status(self, consumed_ml: int, target_ml: int) -> dict:
        pct = (consumed_ml / target_ml * 100) if target_ml > 0 else 0
        remaining = max(0, target_ml - consumed_ml)

        if pct >= 100:
            status, emoji, message = "excellent", "💧✅", "Outstanding! You've hit your water goal!"
        elif pct >= 75:
            status, emoji, message = "good", "💧", f"Almost there! Just {remaining}ml more to go."
        elif pct >= 50:
            status, emoji, message = "fair", "⚠️", f"Halfway there. Drink {remaining}ml more."
        elif pct >= 25:
            status, emoji, message = "low", "🚨", f"Low hydration! You need {remaining}ml more."
        else:
            status, emoji, message = "critical", "🚨🚨", f"Critical! Only {consumed_ml}ml consumed. Drink NOW!"

        return {
            "consumed_ml": consumed_ml,
            "target_ml": target_ml,
            "remaining_ml": remaining,
            "percentage": round(pct, 1),
            "status": status,
            "emoji": emoji,
            "message": message,
            "glasses": round(consumed_ml / 250),
        }

    def format_progress_bar(self, consumed_ml: int, target_ml: int) -> str:
        pct = min(consumed_ml / target_ml, 1.0) if target_ml > 0 else 0
        filled = int(pct * 10)
        return f"{'🟦' * filled}{'⬜' * (10 - filled)} {round(pct * 100)}%"

    def parse_water_amount(self, text: str) -> int | None:
        text = text.lower().strip()
        if "l" in text and "ml" not in text:
            try:
                return int(float(text.replace("litre", "").replace("liter", "").replace("l", "").strip()) * 1000)
            except ValueError:
                pass
        if "ml" in text:
            try:
                return int(float(text.replace("ml", "").strip()))
            except ValueError:
                pass
        if "glass" in text or "cup" in text:
            try:
                return int(float(text.split()[0]) * 250)
            except (ValueError, IndexError):
                return 250
        if "bottle" in text:
            try:
                return int(float(text.split()[0]) * 500)
            except (ValueError, IndexError):
                return 500
        try:
            val = int(float(text.split()[0]))
            if 50 <= val <= 5000:
                return val
        except (ValueError, IndexError):
            pass
        return None

    async def get_hydration_tip(self, user: User, consumed_ml: int, target_ml: int) -> str:
        pct = round(consumed_ml / target_ml * 100) if target_ml > 0 else 0
        return await claude.fast_completion(
            messages=[{"role": "user", "content": f"User has drunk {consumed_ml}ml ({pct}% of {target_ml}ml goal). Give a quick 1-2 sentence hydration tip."}],
            system="You are a hydration coach. Give short, encouraging hydration tips.",
            max_tokens=100,
        )
