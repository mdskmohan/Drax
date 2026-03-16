"""
Health Sync API endpoint.
Receives weight/steps/calories from Apple Health Shortcuts or Android Tasker.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.user import User
from app.models.weight_log import WeightLog
from app.models.water_log import WaterLog

router = APIRouter()


class HealthSyncPayload(BaseModel):
    type: str    # "weight" | "steps" | "calories_burned" | "water"
    value: float
    timestamp: str | None = None


@router.post("/sync/{token}")
async def health_sync(token: str, payload: HealthSyncPayload):
    """Accept health data from iOS Shortcuts or Android automation."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.health_sync_token == token)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=401, detail="Invalid sync token")

        data_type = payload.type.lower()
        value = payload.value

        if data_type == "weight":
            if not 30 <= value <= 300:
                raise HTTPException(status_code=400, detail="Weight must be 30–300 kg")
            log = WeightLog(user_id=user.id, weight_kg=value)
            session.add(log)
            user.current_weight_kg = value

        elif data_type == "water":
            log = WaterLog(user_id=user.id, amount_ml=int(value))
            session.add(log)

        elif data_type in ("steps", "calories_burned"):
            # Store in user context (future: workout_log integration)
            pass

        else:
            raise HTTPException(status_code=400, detail=f"Unknown type: {data_type}")

        await session.commit()

    return {"status": "ok", "type": data_type, "value": value}


@router.get("/sync/{token}")
async def health_sync_info(token: str):
    """Return sync status and accepted data types."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.health_sync_token == token)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=401, detail="Invalid token")

    return {
        "status": "active",
        "user": user.first_name,
        "accepted_types": ["weight", "water", "steps", "calories_burned"],
        "format": {"type": "weight", "value": 85.5},
    }
