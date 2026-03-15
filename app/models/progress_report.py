from sqlalchemy import Column, BigInteger, Integer, Float, DateTime, ForeignKey, Text, JSON, String
from sqlalchemy.sql import func
from app.database import Base


class ProgressReport(Base):
    __tablename__ = "progress_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)

    # Report period
    week_number = Column(Integer, nullable=True)
    report_type = Column(String(20), default="weekly")  # daily/weekly/monthly

    # Summary stats
    avg_daily_calories = Column(Float, nullable=True)
    total_workouts = Column(Integer, default=0)
    workouts_completed = Column(Integer, default=0)
    avg_daily_water_ml = Column(Float, nullable=True)
    weight_start_kg = Column(Float, nullable=True)
    weight_end_kg = Column(Float, nullable=True)
    weight_change_kg = Column(Float, nullable=True)

    # Full AI report
    report_text = Column(Text, nullable=True)
    recommendations = Column(JSON, nullable=True)       # list of recommendation strings

    generated_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    def __repr__(self):
        return f"<ProgressReport id={self.id} user={self.user_id} week={self.week_number}>"
