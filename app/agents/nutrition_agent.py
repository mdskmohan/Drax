"""
Nutrition Agent — Claude Haiku for fast parsing, Claude Sonnet for coaching.
"""
from app.agents.base_agent import BaseAgent
from app.models.user import User
from app.services.llm import llm
from app.services.nutritionix import parse_food_text


NUTRITION_ROLE = """You are a certified nutritionist and dietitian specializing in weight loss.
You help users track their food intake, understand their macros, and make healthier choices.
You follow international nutrition guidelines (WHO, Academy of Nutrition and Dietetics, EFSA).
You balance science-based advice with practical, sustainable eating habits.
You understand various diet preferences (keto, vegetarian, vegan, etc.) and cultural foods including Indian cuisine.
Never be judgmental about food choices — be encouraging and educational.
You provide general nutrition education only — not medical nutrition therapy or treatment for medical conditions.
Always encourage users to consult a Registered Dietitian (RD/RDN) or their doctor for personalised clinical nutrition advice, especially for medical conditions, eating disorders, or pregnancy."""


class NutritionAgent(BaseAgent):

    async def parse_meal(self, user: User, food_text: str) -> dict:
        """Haiku normalizes the text, then Nutritionix fetches macros."""
        result = await llm.json(
            messages=[{"role": "user", "content": food_text}],
            system='Extract and normalize food items from user input. Return JSON: {"normalized_query": "cleaned food description", "meal_type": "breakfast|lunch|dinner|snack"}',
            fast=True,
            max_tokens=150,
        )
        query = result.get("normalized_query", food_text)
        meal_type = result.get("meal_type", "snack")

        nutrition = await parse_food_text(query, timezone=user.timezone or "UTC")
        nutrition["meal_type"] = meal_type
        nutrition["original_input"] = food_text
        return nutrition

    async def analyze_food_photo(self, user: User, image_bytes: bytes, caption: str = "") -> dict:
        """
        Use vision AI to identify food in a photo, then fetch nutrition data.
        Falls back to caption if vision fails.
        """
        caption_hint = f" Caption: '{caption}'" if caption else ""
        prompt = (
            f"Identify all food items visible in this photo.{caption_hint} "
            "List each item with estimated quantity (e.g., '2 boiled eggs', '1 cup white rice', '150g chicken breast'). "
            "Return ONLY a comma-separated list of food items with quantities. No explanation."
        )
        try:
            detected = await llm.vision(
                image_bytes=image_bytes,
                prompt=prompt,
                system="You are a food identification expert. Be precise about portions and quantities.",
            )
            food_description = detected.strip() if detected else (caption or "mixed food plate")
        except Exception:
            food_description = caption or "mixed food plate"

        nutrition = await self.parse_meal(user, food_description)
        nutrition["detected_from_photo"] = True
        nutrition["detected_description"] = food_description
        return nutrition

    async def get_meal_feedback(self, user: User, meal_description: str, nutrition: dict, daily_calories_so_far: float) -> str:
        remaining = (user.daily_calorie_target or 2000) - daily_calories_so_far
        return await llm.fast(
            messages=[{"role": "user", "content": f"""User logged: {meal_description}
Calories: {nutrition.get('total_calories', 0):.0f} kcal | Protein: {nutrition.get('total_protein_g', 0):.0f}g | Carbs: {nutrition.get('total_carbs_g', 0):.0f}g | Fat: {nutrition.get('total_fat_g', 0):.0f}g
Calories today so far: {daily_calories_so_far:.0f} kcal | Remaining: {remaining:.0f} kcal
Give 2-3 sentences of helpful feedback on the meal quality and remaining calorie budget."""}],
            system=self._system_str(NUTRITION_ROLE, user),
            max_tokens=200,
        )

    async def generate_daily_meal_plan(self, user: User) -> dict:
        calorie_target = user.daily_calorie_target or (round(user.tdee - 500) if user.tdee else 1800)
        diet = user.diet_preference.value if user.diet_preference else "omnivore"
        cuisine = getattr(user, "cuisine_preference", None) or "general"
        cuisine_instruction = (
            f"All meals must follow *{cuisine} cuisine* — use traditional ingredients, "
            f"flavour profiles, and cooking methods typical of {cuisine} cooking."
            if cuisine != "general"
            else "Cuisine style: any balanced variety."
        )
        return await llm.json(
            messages=[{"role": "user", "content": f"""Create a complete daily meal plan targeting {calorie_target} calories.
Diet: {diet}
{cuisine_instruction}

Return JSON:
{{
  "calorie_target": {calorie_target},
  "cuisine": "{cuisine}",
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
        return await llm.chat(
            messages=[{"role": "user", "content": f"Weekly nutrition:\n{summary}\n\nProvide analysis covering: calorie adherence, macro balance, 3 actionable tips for next week."}],
            system=self._system_str(NUTRITION_ROLE, user),
            max_tokens=600,
        )

    async def adjust_calorie_target(self, user: User, actual_weight_change: float, expected_change: float) -> int:
        result = await llm.json(
            messages=[{"role": "user", "content": f"""Expected weekly change: {expected_change}kg | Actual: {actual_weight_change}kg | Current target: {user.daily_calorie_target} kcal
Return JSON: {{"new_calorie_target": <int>, "reason": "..."}}"""}],
            system=self._system_str(NUTRITION_ROLE, user),
            fast=True,
            max_tokens=200,
        )
        return int(result.get("new_calorie_target", user.daily_calorie_target or 1800))
