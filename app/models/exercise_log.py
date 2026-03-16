from sqlalchemy import Column, BigInteger, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


class ExerciseLog(Base):
    """
    Records one set (or best set) of a single exercise performed during a workout.
    Used to drive progressive overload — the coach fetches recent history and
    automatically suggests weight/rep increases for the next session.
    """
    __tablename__ = "exercise_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    workout_log_id = Column(Integer, ForeignKey("workout_logs.id"), nullable=True, index=True)

    exercise_name = Column(String(100), nullable=False)
    weight_kg = Column(Float, nullable=True)    # null for bodyweight exercises
    reps = Column(Integer, nullable=True)
    sets = Column(Integer, nullable=True)
    rpe = Column(Float, nullable=True)          # Rate of Perceived Exertion 1–10 (optional)

    logged_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    def __repr__(self):
        return (
            f"<ExerciseLog id={self.id} user={self.user_id} "
            f"exercise={self.exercise_name!r} weight={self.weight_kg}kg "
            f"sets={self.sets}x{self.reps}>"
        )
