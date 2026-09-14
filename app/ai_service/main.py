import os
import json
import re
import traceback
from typing import List, Optional
from datetime import datetime, timezone

from dotenv import load_dotenv
load_dotenv()  # تفعيل تحميل متغيرات البيئة من ملف .env فوراً

from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from groq import Groq
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

# استيراد إعدادات والنماذج الخاصة بقاعدة البيانات
from .database import engine, Base, get_db
from .models import DBPerformanceInsight, DBFeedbackCapture, DBUser
from .auth import verify_password, get_password_hash, create_access_token, get_current_user

# استيراد دوال نظام التقييمات (Feedback System) - تم تعديل المسار ليتوافق مع المجلد الرئيسي
from .feedback_capture import capture_feedback, analyze_feedback
class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "manager"


# إنشاء الجداول تلقائياً في SQLite عند بدء التشغيل
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Smart HR - AI Analytics System")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "your_groq_api_key_here")
client = Groq(api_key=GROQ_API_KEY)

# Global History Database (In-Memory Fallback)
history_db = {}


# ---------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------
class FeedbackCaptureRequest(BaseModel):
    employee_id: str = Field(..., example="EMP-101")
    performance_score: float = Field(..., example=85.0)
    tasks_completed: int = Field(..., example=40)
    feedback: str = Field(..., example="Good team player, delivers code on time.")


class PolicyRequest(BaseModel):
    employee_id: str = Field(..., example="EMP-101")
    question: str = Field(..., example="ما هي سياسة الإجازات السنوية وكيف يمكنني طلب إجازة؟")


class EvaluationDraftRequest(BaseModel):
    employee_id: str = Field(..., example="EMP-101")
    evaluation_period: str = Field(..., example="Q3 2026")
    goals_met: bool = Field(..., example=True)
    manager_notes: Optional[str] = Field(None, example="أظهر التزاماً كبيراً وتطوراً في العمل الجماعي.")


class FeedbackRequest(BaseModel):
    insight_id: str = Field(..., example="INSIGHT-EMP-101-1")
    insight_type: str = Field(..., example="performance_insight")
    user_id: str = Field(..., example="user_123")
    user_role: str = Field(..., example="manager")
    rating: str = Field(..., example="useful")  # useful أو not_useful
    flagged_for_review: bool = Field(False, example=False)
    comment: Optional[str] = Field(None, example="أداء ممتاز وتحليل دقيق")


# ---------------------------------------------------------
# 1. Exception Handling
# ---------------------------------------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "status": "fallback",
            "message": "An internal error occurred. Safe fallback activated.",
            "detail": str(exc)
        }
    )


# ---------------------------------------------------------
# 2. AI Feedback Capture & Analytics (With DB Integration)
# ---------------------------------------------------------
@app.post("/ai/feedback-capture")
@app.post("/performance-insight")
@app.post("/ai/performance-insight")  # <--- تمت إضافة هذا المسار ليتطابق مع طلب الواجهة
def capture_feedback_and_generate_insight(
    payload: FeedbackCaptureRequest, 
    db: Session = Depends(get_db)
):
    insight_id = f"INSIGHT-{payload.employee_id}-{len(history_db) + 1}"
    
    try:
        prompt = f"""
        Analyze the following employee feedback and metrics:
        Employee ID: {payload.employee_id}
        Performance Score: {payload.performance_score}
        Tasks Completed: {payload.tasks_completed}
        Feedback: {payload.feedback}

        Provide a short professional analysis and recommendations in Arabic.
        """
        
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}]
        )
        
        insight_text = response.choices[0].message.content
        
        # 1. حفظ في الـ History (In-Memory)
        history_entry = {
            "insight_id": insight_id,
            "employee_id": payload.employee_id,
            "type": "feedback_insight",
            "score": payload.performance_score,
            "tasks_completed": payload.tasks_completed,
            "feedback": payload.feedback,
            "insight": insight_text,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        history_db[insight_id] = history_entry

        # 2. حفظ دائم في قاعدة البيانات (SQLite)
        db_insight = DBPerformanceInsight(
            insight_id=insight_id,
            employee_id=payload.employee_id,
            overall_score=payload.performance_score,
            summary=insight_text
        )
        db.add(db_insight)
        db.commit()
        db.refresh(db_insight)
        
        return {
            "status": "success",
            "insight_id": insight_id,
            "employee_id": payload.employee_id,
            "insight": insight_text
        }
        
    except Exception as e:
        fallback_entry = {
            "insight_id": insight_id,
            "employee_id": payload.employee_id,
            "type": "feedback_insight",
            "score": payload.performance_score,
            "tasks_completed": payload.tasks_completed,
            "feedback": payload.feedback,
            "insight": f"الأداء مستقر بناءً على التقييم الرقمي ({payload.performance_score}). (Safe Fallback)",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        history_db[insight_id] = fallback_entry

        # حفظ الـ Fallback في قاعدة البيانات أيضاً
        try:
            db_insight = DBPerformanceInsight(
                insight_id=insight_id,
                employee_id=payload.employee_id,
                overall_score=payload.performance_score,
                summary=fallback_entry["insight"]
            )
            db.add(db_insight)
            db.commit()
        except Exception:
            pass
        
        return {
            "status": "fallback",
            "insight_id": insight_id,
            "employee_id": payload.employee_id,
            "insight": fallback_entry["insight"]
        }


# ---------------------------------------------------------
# 3. HR Policy Assistant
# ---------------------------------------------------------
@app.post("/ai/policy-assistant")
def hr_policy_assistant(payload: PolicyRequest):
    try:
        keywords = ["إجازة", "مرتب", "تأمين", "ساعات العمل", "سلفة", "حافز"]
        has_context = any(word in payload.question for word in keywords)
        
        if not has_context:
            return {
                "status": "insufficient_data",
                "answer": "لا تتوفر بيانات كافية أو سياسات معتمدة لإجابة هذا السؤال حالياً.",
                "explanation": "تتطلب الإجابة الرجوع لسياسات الشركة المعتمدة.",
                "policy_reference": "None",
                "missing_context": ["active_policies"]
            }
            
        prompt = f"أجب عن استفسار الموظف التالي بناءً على لوائح العمل العامة: {payload.question}"
        
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}]
        )
        
        return {
            "status": "success",
            "employee_id": payload.employee_id,
            "answer": response.choices[0].message.content
        }
    except Exception as e:
        return {
            "status": "fallback",
            "employee_id": payload.employee_id,
            "answer": "يرجى التواصل مباشرة مع قسم الموارد البشرية عبر البريد الإلكتروني."
        }


# ---------------------------------------------------------
# 4. Insight History & Regeneration (With DB Querying)
# ---------------------------------------------------------
@app.get("/ai/history")
def get_insight_history(db: Session = Depends(get_db)):
    db_records = db.query(DBPerformanceInsight).all()
    
    if db_records:
        formatted_history = [
            {
                "insight_id": record.insight_id,
                "employee_id": record.employee_id,
                "overall_score": record.overall_score,
                "summary": record.summary,
                "created_at": str(record.created_at)
            }
            for record in db_records
        ]
        return {
            "status": "success",
            "source": "database",
            "count": len(formatted_history),
            "history": formatted_history
        }

    return {
        "status": "success",
        "source": "in_memory",
        "count": len(history_db),
        "history": list(history_db.values())
    }


@app.post("/ai/regenerate/{insight_id}")
def regenerate_insight(insight_id: str, db: Session = Depends(get_db)):
    db_insight = db.query(DBPerformanceInsight).filter(DBPerformanceInsight.insight_id == insight_id).first()
    
    if not db_insight and insight_id not in history_db:
        return JSONResponse(
            status_code=404,
            content={"status": "error", "message": f"Insight ID '{insight_id}' not found in history or database."}
        )
    
    employee_id = db_insight.employee_id if db_insight else history_db[insight_id].get("employee_id")
    score = db_insight.overall_score if db_insight else history_db[insight_id].get("score")
    summary_text = db_insight.summary if db_insight else history_db[insight_id].get("insight")
    
    try:
        prompt = f"""
        قم بإعادة تحليل وتقييم أداء الموظف {employee_id} بصياغة جديدة ورؤية أكثر عمقاً:
        درجة الأداء: {score}
        الملخص السابق: {summary_text}
        """
        
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}]
        )
        
        new_insight = response.choices[0].message.content
        
        if db_insight:
            db_insight.summary = new_insight
            db.commit()

        if insight_id in history_db:
            history_db[insight_id]["insight"] = new_insight
            history_db[insight_id]["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            history_db[insight_id]["status"] = "regenerated"
        
        return {
            "status": "success",
            "message": "Insight regenerated successfully",
            "insight_id": insight_id,
            "new_insight": new_insight
        }
    except Exception as e:
        return {
            "status": "fallback",
            "message": "Failed to regenerate, keeping previous insight.",
            "insight_id": insight_id
        }


# ---------------------------------------------------------
# 5. Evaluation Draft Assistant
# ---------------------------------------------------------
@app.post("/ai/evaluation-draft")
def generate_evaluation_draft(payload: EvaluationDraftRequest, db: Session = Depends(get_db)):
    draft_id = f"DRAFT-{payload.employee_id}-{len(history_db) + 1}"
    
    try:
        past_db_insights = db.query(DBPerformanceInsight).filter(DBPerformanceInsight.employee_id == payload.employee_id).all()
        past_insights_texts = [f"Score: {item.overall_score}, Summary: {item.summary}" for item in past_db_insights]
        
        if not past_insights_texts:
            past_insights_texts = [item["insight"] for item in history_db.values() if item.get("employee_id") == payload.employee_id]

        history_context = "\n".join(past_insights_texts) if past_insights_texts else "لا توجد تحليلات سابقة مخزنة."

        prompt = f"""
        اكتب مسودة تقييم أداء رسمية وشاملة (Evaluation Draft) للموظف:
        - كود الموظف: {payload.employee_id}
        - الفترة: {payload.evaluation_period}
        - تحقيق الأهداف: {'نعم' if payload.goals_met else 'لا'}
        - ملاحظات المدير: {payload.manager_notes or 'لا توجد ملاحظات إضافية'}
        - السجل والتحليلات السابقة:
        {history_context}

        صغ التقييم باللغة العربية بأسلوب موارد بشرية احترافي يتضمن:
        1. ملخص الأداء العام.
        2. أبرز نقاط القوة.
        3. مجالات التطوير المقترحة للفترة القادمة.
        """
        
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}]
        )
        
        draft_text = response.choices[0].message.content
        
        history_db[draft_id] = {
            "insight_id": draft_id,
            "employee_id": payload.employee_id,
            "type": "evaluation_draft",
            "evaluation_period": payload.evaluation_period,
            "insight": draft_text,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        return {
            "status": "success",
            "draft_id": draft_id,
            "employee_id": payload.employee_id,
            "evaluation_period": payload.evaluation_period,
            "evaluation_draft": draft_text
        }
        
    except Exception as e:
        return {
            "status": "fallback",
            "draft_id": draft_id,
            "employee_id": payload.employee_id,
            "evaluation_draft": "تم إعداد مسودة مبسطة: الموظف مستمر في تحقيق متطلبات التقييم الدورية. (Safe Fallback)"
        }


# ---------------------------------------------------------
# 6. AI Feedback Management Endpoints (New)
# ---------------------------------------------------------
@app.post("/ai/feedback")
def submit_ai_feedback(payload: FeedbackRequest):
    try:
        record = capture_feedback(
            insight_id=payload.insight_id,
            insight_type=payload.insight_type,
            user_id=payload.user_id,
            user_role=payload.user_role,
            rating=payload.rating,
            flagged_for_review=payload.flagged_for_review,
            comment=payload.comment
        )
        return {
            "status": "success",
            "message": "Feedback captured successfully",
            "data": record
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/ai/feedback/analysis")
def get_ai_feedback_analysis():
    report = analyze_feedback()
    return {
        "status": "success",
        "analysis_report": report
    }


# ---------------------------------------------------------
# 7. Authentication Endpoints
# ---------------------------------------------------------
@app.post("/register")
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(DBUser).filter(DBUser.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    clean_password = user.password.encode('utf-8')[:72].decode('utf-8', errors='ignore')
    hashed_pwd = get_password_hash(clean_password)
    
    new_user = DBUser(username=user.username, hashed_password=hashed_pwd, role=user.role)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"message": "User registered successfully", "username": new_user.username}


@app.post("/token")
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(DBUser).filter(DBUser.username == form_data.username).first()
    
    clean_password = form_data.password.encode('utf-8')[:72].decode('utf-8', errors='ignore')
    if not user or not verify_password(clean_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    
    access_token = create_access_token(data={"sub": user.username, "role": user.role})
    return {"access_token": access_token, "token_type": "bearer"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.ai_service.main:app", host="0.0.0.0", port=8000, reload=True)