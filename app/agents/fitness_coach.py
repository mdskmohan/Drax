"""
Fitness Coach Agent — Claude Sonnet for workout generation, with daily caching.
"""
from collections import defaultdict
from datetime import date
from app.agents.base_agent import BaseAgent
from app.models.user import User
from app.services.llm import llm
from app.services.youtube import get_workout_videos

# Simple in-process daily cache: {(user_id, date, day_of_week) -> plan}
_workout_cache: dict = {}


COACH_ROLE = """You are an expert personal fitness trainer and certified strength & conditioning coach.
Your job is to create safe, effective, progressive workout plans for weight loss and fitness improvement.
You follow ACSM (American College of Sports Medicine) and NSCA exercise guidelines.
Always consider the user's current fitness level, available days, and long-term goals.
Workouts should combine cardio, strength training, and flexibility work appropriately.
Format workouts clearly with sets, reps, rest times, and technique tips.
Be encouraging, specific, and science-based.
Always prioritise safety: include proper warm-up, cooldown, and form cues. For beginners, start conservatively.
You provide general fitness programming — not medical exercise prescription.
If a user reports pain, injury, a chronic health condition, or is post-surgery, always advise them to consult a qualified physiotherapist or sports medicine doctor before continuing.
Remind users: consult a doctor before starting any new exercise programme, particularly if they have cardiovascular, metabolic, or musculoskeletal conditions."""


class FitnessCoachAgent(BaseAgent):

    async def scan_equipment_from_photo(self, image_bytes: bytes) -> dict:
        """Detect gym equipment from a photo using vision AI."""
        prompt = (
            "List all gym equipment you can see in this image. "
            "Return JSON: {\"equipment\": [\"barbell\", \"dumbbells\", ...], \"setup_type\": \"gym|home|bodyweight\"}"
        )
        try:
            result = await llm.vision(
                image_bytes=image_bytes,
                prompt=prompt,
                system="You are a gym equipment expert. Identify EXERCISE and FITNESS equipment only (barbells, dumbbells, machines, benches, cables, etc.). Ignore non-gym objects like furniture, food, or clothing.",
            )
            from app.services.llm import _parse_json
            data = _parse_json(result)
            return {
                "equipment": data.get("equipment", []),
                "setup_type": data.get("setup_type", "gym"),
            }
        except Exception:
            return {"equipment": [], "setup_type": "gym"}

    async def generate_daily_workout(
        self,
        user: User,
        day_of_week: str,
        recent_workouts: list[dict] | None = None,
        is_gym_day: bool = True,
        exercise_history: list[dict] | None = None,
        yesterday_nutrition: dict | None = None,
        recent_workout_history: list[dict] | None = None,
    ) -> dict:
        # Return cached plan if already generated today
        cache_key = (user.id, date.today(), day_of_week)
        if cache_key in _workout_cache:
            return _workout_cache[cache_key]

        recent_summary = f"\nRecent workouts: {recent_workouts}" if recent_workouts else ""

        # ── Live coaching context ─────────────────────────────────────────────
        # Build the context a personal trainer would review before each session:
        # yesterday's nutrition and the last 7 days of workout history.
        coaching_context = ""

        if yesterday_nutrition:
            cal = yesterday_nutrition.get("calories", 0)
            cal_target = user.daily_calorie_target or 2000
            cal_diff = cal - cal_target
            prot = yesterday_nutrition.get("protein_g", 0)
            prot_target = user.protein_target_g or 150
            carbs = yesterday_nutrition.get("carbs_g", 0)
            fat = yesterday_nutrition.get("fat_g", 0)
            water = yesterday_nutrition.get("water_ml", 0)
            water_target = user.daily_water_target_ml or 3000

            coaching_context += (
                f"\n\nYESTERDAY'S NUTRITION:"
                f"\n- Calories: {cal} kcal vs {cal_target} target "
                f"({'OVER' if cal_diff > 0 else 'UNDER'} by {abs(cal_diff)} kcal)"
                f"\n- Protein: {prot}g vs {prot_target}g target "
                f"({'✓ met' if prot >= prot_target * 0.9 else '⚠️ LOW — include protein reminder in coach_tip'})"
                f"\n- Carbs: {carbs}g | Fat: {fat}g"
                f"\n- Water: {water}ml vs {water_target}ml "
                f"({'✓' if water >= water_target * 0.8 else '⚠️ LOW — add hydration cue in coach_tip'})"
            )
            if cal_diff < -400:
                coaching_context += (
                    "\n→ Large caloric deficit yesterday: keep today's intensity moderate, "
                    "emphasise recovery and do not push to failure."
                )
            if prot < prot_target * 0.7:
                coaching_context += (
                    "\n→ Protein very low: stress protein intake urgency in the coach_tip field."
                )

        if recent_workout_history:
            coaching_context += "\n\nRECENT WORKOUT HISTORY (newest first):"
            for wh in recent_workout_history[:7]:
                if wh["completed"] and not wh["skipped"]:
                    status = "✓ Completed"
                elif wh["skipped"]:
                    status = "✗ Skipped"
                else:
                    status = "✗ Not completed"
                pain_flag = " — ⚠️ PAIN reported" if wh["pain_reported"] else ""
                muscles = (
                    f" | Muscles trained: {', '.join(wh['muscle_groups'])}"
                    if wh["muscle_groups"] else ""
                )
                coaching_context += (
                    f"\n  {wh['day_of_week']} {wh['date']}: "
                    f"{wh['workout_type']} — {status}{muscles}{pain_flag}"
                )
            coaching_context += (
                "\n\nINSTRUCTIONS based on history above:"
                "\n- Do NOT programme muscle groups that were trained in the last 48 hours."
                "\n- If the most recent session was skipped or not completed, make today's plan "
                "approachable and motivating rather than punishing."
                "\n- If pain was reported recently, avoid exercises that load those areas."
                "\n- Vary workout type to match the user's weekly pattern (avoid same type 3 days running)."
            )

        # Progressive overload context — format recent performance per exercise
        overload_context = ""
        if exercise_history:
            # Group entries by exercise name (most recent first)
            by_exercise: dict[str, list] = defaultdict(list)
            for entry in exercise_history:
                by_exercise[entry.get("exercise_name", "?")].append(entry)

            lines = ["\nRecent exercise performance (use for progressive overload):"]
            for ex_name, entries in by_exercise.items():
                # entries already ordered most-recent-first from the DB query
                latest = entries[0]
                w = f"{latest['weight_kg']}kg" if latest.get("weight_kg") else "bodyweight"
                reps = latest.get("reps", "?")
                sets = latest.get("sets", "?")
                date_str = latest.get("logged_at", "")[:10]

                # Plateau detection: same weight across last 3+ sessions → suggest +1 set
                same_weight_streak = sum(
                    1 for e in entries[:3]
                    if e.get("weight_kg") and e["weight_kg"] == latest.get("weight_kg")
                )
                if same_weight_streak >= 3 and latest.get("weight_kg"):
                    suggestion = f"plateau detected ({same_weight_streak} sessions at {w}) — add 1 set"
                else:
                    suggestion = "increase weight ~2.5–5% or add 1 rep"

                lines.append(f"  • {ex_name}: {sets}×{reps} @ {w} ({date_str}) → {suggestion}")

            lines.append(
                "For each exercise above, apply the suggestion shown. "
                "Include the recommended weight or sets change in the exercise notes field."
            )
            overload_context = "\n".join(lines)

        # Build equipment context
        if user.equipment_list:
            equipment_context = f"\nAvailable equipment: {', '.join(user.equipment_list)}"
        elif hasattr(user, 'equipment_setup') and user.equipment_setup == "home":
            equipment_context = "\nAvailable equipment: dumbbells, resistance bands, bodyweight only"
        elif hasattr(user, 'equipment_setup') and user.equipment_setup == "bodyweight":
            equipment_context = "\nAvailable equipment: bodyweight only, no equipment"
        else:
            equipment_context = ""

        messages = [
            {
                "role": "user",
                "content": f"""Generate a complete {day_of_week} workout plan.
Is gym day: {is_gym_day}{recent_summary}{equipment_context}{coaching_context}{overload_context}
Customize ALL exercises based on available equipment above.
Use the coaching context above exactly as a personal trainer would — respect muscle group recovery, nutrition status, and session history.
Where exercise history is provided above, apply progressive overload and include the suggested weight in the exercise notes.

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
            messages, system=self._system_str(COACH_ROLE, user), max_tokens=4096
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
