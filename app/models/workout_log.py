from sqlalchemy import Column, BigInteger, Integer, String, Float, DateTime, ForeignKey, Text, JSON, Boolean
from sqlalchemy.sql import func
from app.database import Base


class WorkoutLog(Base):
    __tablename__ = "workout_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)

    # Workout details
    workout_type = Column(String(50), nullable=True)    # strength/cardio/hiit/yoga
    workout_plan = Column(JSON, nullable=True)           # full AI-generated plan
    exercises = Column(JSON, nullable=True)              # list of exercises done

    # Stats
    duration_minutes = Column(Integer, nullable=True)
    calories_burned = Column(Float, nullable=True)

    # Status
    completed = Column(Boolean, default=False)
    completion_notes = Column(Text, nullable=True)      # user feedback
    pain_reported = Column(Boolean, default=False)
    pain_description = Column(Text, nullable=True)

    # AI
    ai_generated_plan = Column(Text, nullable=True)    # full formatted plan text
    youtube_links = Column(JSON, nullable=True)         # video URLs for exercises

    scheduled_date = Column(DateTime(timezone=True), nullable=True, index=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<WorkoutLog id={self.id} user={self.user_id} completed={self.completed}>"
