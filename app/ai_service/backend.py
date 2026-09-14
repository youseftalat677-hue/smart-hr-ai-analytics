from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from passlib.context import CryptContext
import jwt

SECRET_KEY = "smart_hr_super_secret_key"
ALGORITHM = "HS256"

SQLALCHEMY_DATABASE_URL = "sqlite:///./smart_hr.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

class UserDB(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    role = Column(String, default="manager")

class HistoryDB(Base):
    __tablename__ = "history"
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(String, index=True)
    score = Column(Float)
    overall_score = Column(Float)
    tasks_completed = Column(Integer)
    feedback = Column(Text)
    insight_type = Column(String, default="performance_insight")

class FeedbackDB(Base):
    __tablename__ = "feedback"
    id = Column(Integer, primary_key=True, index=True)
    insight_id = Column(String)
    insight_type = Column(String)
    user_id = Column(String)
    user_role = Column(String)
    rating = Column(String)
    flagged_for_review = Column(Boolean)
    comment = Column(Text)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Smart HR AI API - SQLite Persistent")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_password_hash(password):
    return pwd_context.hash(password)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

class UserRegister(BaseModel):
    username: str
    password: str
    role: str = "manager"

class PerformanceInput(BaseModel):
    employee_id: str
    performance_score: float
    tasks_completed: int
    feedback: str

class PolicyInput(BaseModel):
    employee_id: str
    question: str

class EvaluationInput(BaseModel):
    employee_id: str
    evaluation_period: str
    goals_met: bool
    manager_notes: str

class FeedbackInput(BaseModel):
    insight_id: str
    insight_type: str
    user_id: str
    user_role: str
    rating: str
    flagged_for_review: bool
    comment: str

@app.get("/")
def read_root():
    return {"message": "Smart HR AI Backend is running with SQLite persistence."}

@app.post("/register")
def register_user(user: UserRegister, db: Session = Depends(get_db)):
    existing = db.query(UserDB).filter(UserDB.username == user.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already registered")
    hashed_pw = get_password_hash(user.password)
    new_user = UserDB(username=user.username, hashed_password=hashed_pw, role=user.role)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"status": "success", "username": new_user.username, "role": new_user.role}

@app.post("/token")
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(UserDB).filter(UserDB.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")
    token_data = {"sub": user.username, "role": user.role}
    access_token = jwt.encode(token_data, SECRET_KEY, algorithm=ALGORITHM)
    return {"access_token": access_token, "token_type": "bearer", "role": user.role}

@app.post("/ai/performance-insight")
def performance_insight(data: PerformanceInput, db: Session = Depends(get_db)):
    insight_text = f"تقرير الأداء للموظف {data.employee_id}: الدرجة {data.performance_score}%. تم انجاز {data.tasks_completed} مهمة. التوصية: الاستمرار في الأداء المتميز وتطوير المهارات القيادية."
    
    db_item = HistoryDB(
        employee_id=data.employee_id,
        score=data.performance_score,
        overall_score=data.performance_score,
        tasks_completed=data.tasks_completed,
        feedback=data.feedback,
        insight_type="performance_insight"
    )
    db.add(db_item)
    db.commit()
    
    return {"status": "success", "insight": insight_text, "employee_id": data.employee_id}

@app.post("/ai/policy-assistant")
def policy_assistant(data: PolicyInput):
    return {"answer": f"إجابة سياسة الموارد البشرية للموظف {data.employee_id}: بناءً على لوائح الشركة، يحق للموظف الحصول على إجازة سنوية مدفوعة الأجر وفقاً للعقد المبرم."}

@app.post("/ai/evaluation-draft")
def evaluation_draft(data: EvaluationInput, db: Session = Depends(get_db)):
    draft = f"### مسودة تقييم الأداء للفترة: {data.evaluation_period}\n- **رقم الموظف:** {data.employee_id}\n- **تحقيق الأهداف:** {'نعم' if data.goals_met else 'لا'}\n- **ملاحظات المدير:** {data.manager_notes}\n- **التقييم العام:** مرضي ويُنصح بالترقية."
    
    db_item = HistoryDB(
        employee_id=data.employee_id,
        score=88.0,
        overall_score=88.0,
        tasks_completed=35,
        feedback=data.manager_notes,
        insight_type="evaluation_draft"
    )
    db.add(db_item)
    db.commit()
    
    return {"status": "success", "evaluation_draft": draft}

@app.get("/ai/history")
def get_history(db: Session = Depends(get_db)):
    records = db.query(HistoryDB).all()
    history_list = []
    for r in records:
        history_list.append({
            "id": r.id,
            "employee_id": r.employee_id,
            "score": r.score,
            "overall_score": r.overall_score,
            "tasks_completed": r.tasks_completed,
            "feedback": r.feedback,
            "insight_type": r.insight_type
        })
    return {"source": "SQLite Database", "history": history_list}

@app.post("/ai/feedback")
def post_feedback(data: FeedbackInput, db: Session = Depends(get_db)):
    db_fb = FeedbackDB(
        insight_id=data.insight_id,
        insight_type=data.insight_type,
        user_id=data.user_id,
        user_role=data.user_role,
        rating=data.rating,
        flagged_for_review=data.flagged_for_review,
        comment=data.comment
    )
    db.add(db_fb)
    db.commit()
    return {"status": "success", "data": data.dict()}

@app.get("/ai/feedback/analysis")
def feedback_analysis(db: Session = Depends(get_db)):
    feedbacks = db.query(FeedbackDB).all()
    total = len(feedbacks)
    useful_count = sum(1 for f in feedbacks if f.rating == "useful")
    return {
        "analysis_report": {
            "total_feedbacks": total,
            "useful_percentage": (useful_count / total * 100) if total > 0 else 0.0
        }
    }