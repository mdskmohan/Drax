"""
Adaptation Agent — runs every week after the weekly report.

Analyses 4 weeks of real performance data and updates the user's
adaptation_profile, which is then injected into every single LLM call
(workout, meals, motivation, progress) so every decision is shaped by
what Drax has actually learned about this specific person.

What gets learned:
- Training phase (cutting / maintaining / building) from weight trend
- Mesocycle week (1-4); week 4 is automatically a deload week
- Chronic pain areas from all reported pain descriptions
- Consistent skip days (days with 2+ skips in 4 weeks)
- 4-week rolling averages: calorie adherence, protein adherence,
  workout completion rate, average weekly weight change
- AI-written coach observations (natural language pattern summary)
- Recommended training split for this specific user
- Intensity recommendation based on completion rate and recovery signals
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from app.agents.base_agent import BaseAgent
from app.models.user import User
from app.services.llm import llm


_ROLE = """You are an elite personal trainer and sports scientist conducting a
monthly client review. You have 4 weeks of detailed performance data.
Your job is to identify patterns, make evidence-based observations, and
write actionable coaching recommendations that will be injected into
every future training and nutrition decision for this client.
Be specific, honest, and personalised — generic advice is useless here."""


class AdaptationAgent(BaseAgent):

    async def analyze_and_update(
        self,
        user: User,
        four_week_data: dict,
    ) -> dict:
        """
        Run full 4-week retrospective. Returns an updated adaptation_profile
        dict ready to be stored to user.adaptation_profile.

        four_week_data keys:
          weight_logs  — list of {"weight_kg": float, "logged_at": str}
          meal_logs    — list of {"calories": float, "protein_g": float, "logged_at": str}
          workout_logs — list of {"completed": bool, "skipped": bool,
                                  "day_of_week": str, "workout_type": str,
                                  "pain_description": str|None, "muscle_groups": list}
        """
        weight_logs  = four_week_data.get("weight_logs", [])
        meal_logs    = four_week_data.get("meal_logs", [])
        workout_logs = four_week_data.get("workout_logs", [])

        # ── 1. Weight trend & training phase ────────────────────────────────
        if len(weight_logs) >= 2:
            total_change = weight_logs[-1]["weight_kg"] - weight_logs[0]["weight_kg"]
            avg_weekly_change = round(total_change / 4, 2)
            if total_change < -0.8:
                training_phase = "cutting"
            elif total_change > 0.8:
                training_phase = "building"
            else:
                training_phase = "maintaining"
        else:
            avg_weekly_change = 0.0
            # Default to cutting if user has a weight loss goal
            w_diff = (user.current_weight_kg or 0) - (user.goal_weight_kg or 0)
            training_phase = "cutting" if w_diff > 2 else "maintaining"

        # ── 2. Calorie & protein adherence (4-week rolling) ─────────────────
        cal_target  = user.daily_calorie_target or 2000
        prot_target = user.protein_target_g or 150

        if meal_logs:
            daily_cals  = defaultdict(float)
            daily_prot  = defaultdict(float)
            for m in meal_logs:
                day = str(m.get("logged_at", ""))[:10]
                daily_cals[day]  += m.get("calories", 0)
                daily_prot[day]  += m.get("protein_g", 0)

            days_tracked       = len(daily_cals)
            days_on_cal_target = sum(1 for c in daily_cals.values() if c >= cal_target * 0.85)
            avg_cal_adherence  = round(days_on_cal_target / days_tracked * 100) if days_tracked else 0

            avg_daily_prot      = sum(daily_prot.values()) / days_tracked if days_tracked else 0
            avg_prot_adherence  = round(avg_daily_prot / prot_target * 100) if prot_target else 0
        else:
            avg_cal_adherence  = 0
            avg_prot_adherence = 0

        # ── 3. Workout completion rate & skip patterns ───────────────────────
        total_sessions    = len(workout_logs)
        completed_sessions = sum(1 for w in workout_logs if w.get("completed") and not w.get("skipped"))
        completion_rate   = round(completed_sessions / total_sessions, 2) if total_sessions else 1.0

        skip_counts: dict[str, int] = defaultdict(int)
        for w in workout_logs:
            if w.get("skipped") or not w.get("completed"):
                day = w.get("day_of_week", "")
                if day:
                    skip_counts[day] += 1
        # Only flag days skipped 2+ times in 4 weeks — that's a real pattern
        skip_patterns = {day: count for day, count in skip_counts.items() if count >= 2}

        # ── 4. Chronic pain areas ────────────────────────────────────────────
        # Collect all pain descriptions from the past 4 weeks; deduplicate
        pain_descriptions = [
            w["pain_description"] for w in workout_logs
            if w.get("pain_description")
        ]
        # Keep the 8 most recent distinct descriptions
        seen: set[str] = set()
        chronic_pain_areas: list[str] = []
        for desc in reversed(pain_descriptions):
            key = desc[:40].lower()
            if key not in seen:
                seen.add(key)
                chronic_pain_areas.insert(0, desc)
            if len(chronic_pain_areas) >= 8:
                break

        # ── 5. Mesocycle week ────────────────────────────────────────────────
        # Standard 4-week block: wk1 base → wk2 volume+ → wk3 intensity+ → wk4 deload
        current_profile  = getattr(user, "adaptation_profile", None) or {}
        prev_meso_week   = current_profile.get("mesocycle_week", 0)
        new_meso_week    = (prev_meso_week % 4) + 1
        meso_started_at  = current_profile.get(
            "mesocycle_started_at",
            datetime.now(timezone.utc).isoformat(),
        )
        if new_meso_week == 1:
            # Starting a new mesocycle
            meso_started_at = datetime.now(timezone.utc).isoformat()

        # ── 6. Dominant workout type ─────────────────────────────────────────
        type_counts: dict[str, int] = defaultdict(int)
        for w in workout_logs:
            t = w.get("workout_type", "")
            if t:
                type_counts[t] += 1
        dominant_type = max(type_counts, key=type_counts.get) if type_counts else "strength"

        # ── 7. Intensity recommendation ──────────────────────────────────────
        if completion_rate >= 0.85:
            intensity_rec = "high"
        elif completion_rate >= 0.65:
            intensity_rec = "moderate"
        else:
            intensity_rec = "low"   # struggling to complete — simplify first

        # ── 8. AI coach observations & split recommendation ──────────────────
        skip_str   = (
            ", ".join(f"{d} ({c}x)" for d, c in skip_patterns.items())
            or "None identified"
        )
        pain_str   = "; ".join(chronic_pain_areas[-3:]) or "None reported"
        muscle_counts: dict[str, int] = defaultdict(int)
        for w in workout_logs:
            for mg in w.get("muscle_groups", []):
                if mg:
                    muscle_counts[mg] += 1
        top_muscles = sorted(muscle_counts, key=muscle_counts.get, reverse=True)[:5]

        summary = (
            f"CLIENT 4-WEEK PERFORMANCE REVIEW\n"
            f"Training phase: {training_phase}\n"
            f"Weight change: {avg_weekly_change:+.2f} kg/week average\n"
            f"Calorie adherence: {avg_cal_adherence}% of days on target (target {cal_target} kcal)\n"
            f"Protein adherence: {avg_prot_adherence}% of daily protein target ({prot_target}g)\n"
            f"Workout completion rate: {int(completion_rate * 100)}% "
            f"({completed_sessions}/{total_sessions} sessions)\n"
            f"Consistent skip days: {skip_str}\n"
            f"Dominant workout type: {dominant_type}\n"
            f"Most trained muscles: {', '.join(top_muscles) or 'insufficient data'}\n"
            f"Pain reports: {pain_str}\n"
            f"Gym days/week: {user.gym_days_per_week}\n"
            f"Fitness level: {user.workout_level.value if user.workout_level else 'beginner'}\n"
            f"Goal: lose {user.weight_to_lose_kg or '?'} kg in {user.timeline_months or 10} months\n"
        )

        ai_result = await llm.json(
            messages=[{
                "role": "user",
                "content": (
                    f"{summary}\n\n"
                    "Based on this data, provide:\n"
                    "1. coach_observations: 2-3 specific, honest sentences about this client's "
                    "patterns and what they mean for their training. Name actual numbers.\n"
                    "2. recommended_split: the best training split for their gym days and level "
                    "(e.g. 'Push/Pull/Legs', 'Upper/Lower', 'Full Body 3x', 'Bro Split')\n"
                    "3. key_focus_areas: list of 2-3 highest-leverage things to improve\n\n"
                    'Return JSON: {"coach_observations": "...", "recommended_split": "...", '
                    '"key_focus_areas": ["...", "..."]}'
                ),
            }],
            system=self._system_str(_ROLE, user),
            fast=True,
            max_tokens=400,
        )

        return {
            "training_phase":              training_phase,
            "mesocycle_week":              new_meso_week,
            "mesocycle_started_at":        meso_started_at,
            "avg_weekly_weight_change_kg": avg_weekly_change,
            "avg_calorie_adherence_pct":   avg_cal_adherence,
            "avg_protein_adherence_pct":   avg_prot_adherence,
            "avg_workout_completion_rate": completion_rate,
            "skip_patterns":               skip_patterns,
            "chronic_pain_areas":          chronic_pain_areas,
            "dominant_workout_type":       dominant_type,
            "intensity_recommendation":    intensity_rec,
            "recommended_split":           ai_result.get("recommended_split", ""),
            "coach_observations":          ai_result.get("coach_observations", ""),
            "key_focus_areas":             ai_result.get("key_focus_areas", []),
            "last_updated_at":             datetime.now(timezone.utc).isoformat(),
        }
