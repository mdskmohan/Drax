"""
Nutrition Agent — Claude Haiku for fast parsing, Claude Sonnet for coaching.
"""
from app.agents.base_agent import BaseAgent
from app.models.user import User
from app.services import claude
from app.services.nutritionix import parse_food_text


NUTRITION_ROLE = """You are a certified nutritionist and dietitian specializing in weight loss.
You help users track their food intake, understand their macros, and make healthier choices.
You balance science-based advice with practical, sustainable eating habits.
You understand various diet preferences (keto, vegetarian, vegan, etc.) and cultural foods including Indian cuisine.
Never be judgmental about food choices — be encouraging and educational."""


class NutritionAgent(BaseAgent):

    async def parse_meal(self, user: User, food_text: str) -> dict:
        """Haiku normalizes the text, then Nutritionix fetches macros."""
        result = await claude.json_completion(
            messages=[{"role": "user", "content": food_text}],
            system='Extract and normalize food items from user input. Return JSON: {"normalized_query": "cleaned food description", "meal_type": "breakfast|lunch|dinner|snack"}',
            fast=True,
            max_tokens=150,
        )
        query = result.get("normalized_query", food_text)
        meal_type = result.get("meal_type", "snack")

        nutrition = await parse_food_text(query)
        nutrition["meal_type"] = meal_type
        nutrition["original_input"] = food_text
        return nutrition

    async def get_meal_feedback(self, user: User, meal_description: str, nutrition: dict, daily_calories_so_far: float) -> str:
        remaining = (user.daily_calorie_target or 2000) - daily_calories_so_far
        return await claude.fast_completion(
            messages=[{"role": "user", "content": f"""User logged: {meal_description}
Calories: {nutrition.get('total_calories', 0):.0f} kcal | Protein: {nutrition.get('total_protein_g', 0):.0f}g | Carbs: {nutrition.get('total_carbs_g', 0):.0f}g | Fat: {nutrition.get('total_fat_g', 0):.0f}g
Calories today so far: {daily_calories_so_far:.0f} kcal | Remaining: {remaining:.0f} kcal
Give 2-3 sentences of helpful feedback on the meal quality and remaining calorie budget."""}],
            system=self._system_str(NUTRITION_ROLE, user),
            max_tokens=200,
        )

    async def generate_daily_meal_plan(self, user: User) -> dict:
        calorie_target = user.daily_calorie_target or (round(user.tdee - 500) if user.tdee else 1800)
        return await claude.json_completion(
            messages=[{"role": "user", "content": f"""Create a complete daily meal plan targeting {calorie_target} calories.
Diet: {user.diet_preference.value if user.diet_preference else 'omnivore'}

Return JSON:
{{
  "calorie_target": {calorie_target},
  "meals": {{
    "breakfast": {{"description": "...", "calories": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0, "prep_time_min": 0}},
    "lunch": {{"description": "...", "calories": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0, "prep_time_min": 0}},
    "dinner": {{"description": "...", "calories": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0, "prep_time_min": 0}},
    "snacks": {{"description": "...", "calories": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0}}
  }},
  "total_calories": 0,
  "total_protein_g": 0,
  "nutrition_tip": "...",
  "formatted_plan": "Full formatted plan text"
}}"""}],
            system=self._system_str(NUTRITION_ROLE, user),
            max_tokens=2000,
        )

    async def analyze_weekly_nutrition(self, user: User, weekly_logs: list[dict]) -> str:
        total = sum(l.get("calories", 0) for l in weekly_logs)
        avg = total / len(weekly_logs) if weekly_logs else 0
        summary = f"Days tracked: {len(weekly_logs)}, Avg daily calories: {round(avg)} kcal"
        return await claude.chat_completion(
            messages=[{"role": "user", "content": f"Weekly nutrition:\n{summary}\n\nProvide analysis covering: calorie adherence, macro balance, 3 actionable tips for next week."}],
            system=self._system_str(NUTRITION_ROLE, user),
            max_tokens=600,
        )

    async def adjust_calorie_target(self, user: User, actual_weight_change: float, expected_change: float) -> int:
        result = await claude.json_completion(
            messages=[{"role": "user", "content": f"""Expected weekly change: {expected_change}kg | Actual: {actual_weight_change}kg | Current target: {user.daily_calorie_target} kcal
Return JSON: {{"new_calorie_target": <int>, "reason": "..."}}"""}],
            system=self._system_str(NUTRITION_ROLE, user),
            fast=True,
            max_tokens=200,
        )
        return int(result.get("new_calorie_target", user.daily_calorie_target or 1800))
