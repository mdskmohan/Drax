from sqlalchemy import Column, BigInteger, Integer, Float, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from app.database import Base


class WeightLog(Base):
    __tablename__ = "weight_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)

    weight_kg = Column(Float, nullable=False)
    body_fat_pct = Column(Float, nullable=True)
    note = Column(Text, nullable=True)
    ai_feedback = Column(Text, nullable=True)

    logged_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    def __repr__(self):
        return f"<WeightLog id={self.id} user={self.user_id} kg={self.weight_kg}>"
