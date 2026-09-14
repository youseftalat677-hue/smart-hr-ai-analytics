from sqlalchemy import Column, Integer, String, Text, Float, DateTime
from datetime import datetime
from .database import Base

class DBPerformanceInsight(Base):
    __tablename__ = "performance_insights"

    id = Column(Integer, primary_key=True, index=True)
    insight_id = Column(String, unique=True, index=True)
    employee_id = Column(String, index=True)
    overall_score = Column(Float)
    summary = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

class DBFeedbackCapture(Base):
    __tablename__ = "feedback_captures"

    id = Column(Integer, primary_key=True, index=True)
    insight_id = Column(String)
    user_id = Column(String)
    user_role = Column(String)
    rating = Column(String)
    comment = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class DBUser(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="manager")