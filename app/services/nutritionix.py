"""
Nutritionix API service.
Parses food text and returns calorie/macro data.
Docs: https://trackapi.nutritionix.com/docs/
"""
import httpx
from app.config import settings


NUTRITIONIX_NLP_URL = "https://trackapi.nutritionix.com/v2/natural/nutrients"
NUTRITIONIX_SEARCH_URL = "https://trackapi.nutritionix.com/v2/search/instant"

_headers = {
    "x-app-id": settings.nutritionix_app_id,
    "x-app-key": settings.nutritionix_api_key,
    "Content-Type": "application/json",
}


async def parse_food_text(food_text: str, timezone: str = "UTC") -> dict:
    """
    Parse natural language food description into nutrition data.
    Returns dict with: foods list, total calories, protein, carbs, fat.
    """
    if not settings.nutritionix_app_id:
        return _mock_nutrition(food_text)

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            NUTRITIONIX_NLP_URL,
            headers=_headers,
            json={"query": food_text, "timezone": timezone},
        )
        if resp.status_code != 200:
            return _mock_nutrition(food_text)

        data = resp.json()
        foods = data.get("foods", [])

        total_calories = sum(f.get("nf_calories", 0) for f in foods)
        total_protein = sum(f.get("nf_protein", 0) for f in foods)
        total_carbs = sum(f.get("nf_total_carbohydrate", 0) for f in foods)
        total_fat = sum(f.get("nf_total_fat", 0) for f in foods)
        total_fiber = sum(f.get("nf_dietary_fiber", 0) for f in foods)
        total_sodium = sum(f.get("nf_sodium", 0) for f in foods)

        parsed_foods = [
            {
                "name": f.get("food_name", "Unknown"),
                "serving_qty": f.get("serving_qty", 1),
                "serving_unit": f.get("serving_unit", "serving"),
                "calories": f.get("nf_calories", 0),
                "protein_g": f.get("nf_protein", 0),
                "carbs_g": f.get("nf_total_carbohydrate", 0),
                "fat_g": f.get("nf_total_fat", 0),
                "thumb": f.get("photo", {}).get("thumb", ""),
            }
            for f in foods
        ]

        return {
            "foods": parsed_foods,
            "total_calories": round(total_calories, 1),
            "total_protein_g": round(total_protein, 1),
            "total_carbs_g": round(total_carbs, 1),
            "total_fat_g": round(total_fat, 1),
            "total_fiber_g": round(total_fiber, 1),
            "total_sodium_mg": round(total_sodium, 1),
        }


async def search_food(query: str) -> list[dict]:
    """Search for food items by name."""
    if not settings.nutritionix_app_id:
        return []

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            NUTRITIONIX_SEARCH_URL,
            headers=_headers,
            params={"query": query, "detailed": True},
        )
        if resp.status_code != 200:
            return []

        data = resp.json()
        items = data.get("common", [])[:5]
        return [{"name": i.get("food_name"), "tag": i.get("tag_name")} for i in items]


def _mock_nutrition(food_text: str) -> dict:
    """Fallback when Nutritionix is not configured — rough estimate."""
    words = food_text.lower().split()
    estimated_cal = 200 + len(words) * 15
    return {
        "foods": [{"name": food_text, "calories": estimated_cal}],
        "total_calories": float(estimated_cal),
        "total_protein_g": estimated_cal * 0.15 / 4,
        "total_carbs_g": estimated_cal * 0.50 / 4,
        "total_fat_g": estimated_cal * 0.35 / 9,
        "total_fiber_g": 3.0,
        "total_sodium_mg": 400.0,
        "note": "Estimated — Nutritionix not configured",
    }
