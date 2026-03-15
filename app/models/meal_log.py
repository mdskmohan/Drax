from sqlalchemy import Column, BigInteger, Integer, String, Float, DateTime, ForeignKey, Text, JSON
from sqlalchemy.sql import func
from app.database import Base


class MealLog(Base):
    __tablename__ = "meal_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)

    # Meal details
    meal_type = Column(String(20), nullable=True)    # breakfast/lunch/dinner/snack
    food_description = Column(Text, nullable=False)  # raw user input
    parsed_foods = Column(JSON, nullable=True)        # list of parsed food items

    # Nutrition (from Nutritionix)
    calories = Column(Float, default=0.0)
    protein_g = Column(Float, default=0.0)
    carbs_g = Column(Float, default=0.0)
    fat_g = Column(Float, default=0.0)
    fiber_g = Column(Float, default=0.0)
    sodium_mg = Column(Float, default=0.0)

    # Source
    source = Column(String(20), default="text")      # text / photo
    photo_file_id = Column(String(200), nullable=True)

    # AI feedback
    ai_feedback = Column(Text, nullable=True)

    logged_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    def __repr__(self):
        return f"<MealLog id={self.id} user={self.user_id} cal={self.calories}>"
