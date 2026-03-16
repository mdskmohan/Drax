from sqlalchemy import Column, BigInteger, String, Float, Integer, Boolean, DateTime, Enum as SAEnum, JSON
from sqlalchemy.sql import func
import enum
from app.database import Base


class DietPreference(str, enum.Enum):
    omnivore = "omnivore"
    vegetarian = "vegetarian"
    vegan = "vegan"
    keto = "keto"
    paleo = "paleo"


class WorkoutLevel(str, enum.Enum):
    beginner = "beginner"
    intermediate = "intermediate"
    advanced = "advanced"


class OnboardingState(str, enum.Enum):
    not_started = "not_started"
    collecting_name = "collecting_name"
    collecting_age = "collecting_age"
    collecting_gender = "collecting_gender"
    collecting_height = "collecting_height"
    collecting_weight = "collecting_weight"
    collecting_goal_weight = "collecting_goal_weight"
    collecting_timeline = "collecting_timeline"
    collecting_diet = "collecting_diet"
    collecting_workout_level = "collecting_workout_level"
    collecting_gym_days = "collecting_gym_days"
    collecting_gym_schedule = "collecting_gym_schedule"
    collecting_equipment = "collecting_equipment"
    collecting_language = "collecting_language"
    completed = "completed"


class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True)           # Telegram user ID
    telegram_username = Column(String(100), nullable=True)
    first_name = Column(String(100), nullable=True)
    full_name = Column(String(200), nullable=True)

    # Physical profile
    age = Column(Integer, nullable=True)
    gender = Column(String(10), nullable=True)
    height_cm = Column(Float, nullable=True)
    current_weight_kg = Column(Float, nullable=True)
    goal_weight_kg = Column(Float, nullable=True)
    timeline_months = Column(Integer, nullable=True)

    # Preferences
    diet_preference = Column(SAEnum(DietPreference), default=DietPreference.omnivore)
    workout_level = Column(SAEnum(WorkoutLevel), default=WorkoutLevel.beginner)
    gym_days_per_week = Column(Integer, default=3)
    gym_schedule = Column(JSON, default=list)           # ["Monday", "Wednesday", "Friday"]
    language = Column(String(10), default="en")         # en | hi | es | fr | ar | etc.

    # Computed targets
    daily_calorie_target = Column(Integer, nullable=True)
    daily_water_target_ml = Column(Integer, default=3000)
    weekly_weight_loss_target_kg = Column(Float, nullable=True)

    # Macro targets (calculated after onboarding)
    protein_target_g = Column(Integer, nullable=True)   # grams/day
    carbs_target_g = Column(Integer, nullable=True)     # grams/day
    fat_target_g = Column(Integer, nullable=True)       # grams/day

    # Gym equipment
    equipment_list = Column(JSON, default=list)         # ["barbell", "dumbbells", "cable machine", ...]
    equipment_setup = Column(String(20), default="gym") # gym | home | bodyweight

    # Apple Health / Google Health Connect sync
    health_sync_token = Column(String(64), nullable=True, unique=True)

    # State
    onboarding_state = Column(
        SAEnum(OnboardingState), default=OnboardingState.not_started
    )
    is_active = Column(Boolean, default=True)
    timezone = Column(String(50), default="Asia/Kolkata")

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_active_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<User id={self.id} name={self.full_name}>"

    @property
    def bmr(self) -> float | None:
        if not all([self.current_weight_kg, self.height_cm, self.age, self.gender]):
            return None
        if self.gender == "male":
            return 10 * self.current_weight_kg + 6.25 * self.height_cm - 5 * self.age + 5
        return 10 * self.current_weight_kg + 6.25 * self.height_cm - 5 * self.age - 161

    @property
    def tdee(self) -> float | None:
        if self.bmr is None:
            return None
        multiplier = {
            "beginner": 1.375,
            "intermediate": 1.55,
            "advanced": 1.725,
        }.get(str(self.workout_level.value if self.workout_level else "beginner"), 1.375)
        return self.bmr * multiplier

    @property
    def weight_to_lose_kg(self) -> float | None:
        if self.current_weight_kg and self.goal_weight_kg:
            return self.current_weight_kg - self.goal_weight_kg
        return None

    def calculate_macros(self):
        """Calculate and set macro targets based on calorie goal (high-protein for fat loss)."""
        cal = self.daily_calorie_target or 1800
        self.protein_target_g = round(cal * 0.35 / 4)   # 35% protein
        self.fat_target_g = round(cal * 0.30 / 9)        # 30% fat
        self.carbs_target_g = round(cal * 0.35 / 4)      # 35% carbs
