from sqlalchemy import Column, BigInteger, Integer, Float, DateTime, ForeignKey, String
from sqlalchemy.sql import func
from app.database import Base


class WaterLog(Base):
    __tablename__ = "water_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)

    amount_ml = Column(Float, nullable=False)
    note = Column(String(100), nullable=True)   # e.g. "morning glass", "gym bottle"

    logged_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    def __repr__(self):
        return f"<WaterLog id={self.id} user={self.user_id} ml={self.amount_ml}>"
