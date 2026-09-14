import json
import re
import traceback
from typing import List, Optional
from datetime import datetime

from fastapi import FastAPI, Request, Depends
from fastapi.responses import JSONResponse
from groq import Groq
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

# استيراد إعدادات والنماذج الخاصة بقاعدة البيانات
from .database import engine, Base, get_db
from .models import DBPerformanceInsight, DBFeedbackCapture

# إنشاء الجداول تلقائياً في SQLite عند بدء التشغيل
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Smart HR - AI Analytics System")

import os

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


# ---------------------------------------------------------
# 1. Safe Fallback Behavior (Global Handler)
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
            performance_score=payload.performance_score,
            tasks_completed=payload.tasks_completed,
            feedback=payload.feedback
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
                performance_score=payload.performance_score,
                tasks_completed=payload.tasks_completed,
                feedback=payload.feedback
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
    # استرجاع البيانات المباشرة من قاعدة البيانات أولاً
    db_records = db.query(DBPerformanceInsight).all()
    
    if db_records:
        formatted_history = [
            {
                "insight_id": record.insight_id,
                "employee_id": record.employee_id,
                "performance_score": record.performance_score,
                "tasks_completed": record.tasks_completed,
                "feedback": record.feedback,
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

    # القراءة من الـ Memory في حالة الفلباك
    return {
        "status": "success",
        "source": "in_memory",
        "count": len(history_db),
        "history": list(history_db.values())
    }


@app.post("/ai/regenerate/{insight_id}")
def regenerate_insight(insight_id: str, db: Session = Depends(get_db)):
    # البحث في قاعدة البيانات أولاً لتلافي مشكلة الـ 404
    db_insight = db.query(DBPerformanceInsight).filter(DBPerformanceInsight.insight_id == insight_id).first()
    
    if not db_insight and insight_id not in history_db:
        return JSONResponse(
            status_code=404,
            content={"status": "error", "message": f"Insight ID '{insight_id}' not found in history or database."}
        )
    
    # تحضير البيانات المطلوبة لإعادة التوليد
    employee_id = db_insight.employee_id if db_insight else history_db[insight_id].get("employee_id")
    score = db_insight.performance_score if db_insight else history_db[insight_id].get("score")
    tasks = db_insight.tasks_completed if db_insight else history_db[insight_id].get("tasks_completed")
    feedback = db_insight.feedback if db_insight else history_db[insight_id].get("feedback")
    
    try:
        prompt = f"""
        قم بإعادة تحليل وتقييم أداء الموظف {employee_id} بصياغة جديدة ورؤية أكثر عمقاً:
        درجة الأداء: {score}
        المهام المكتملة: {tasks}
        الملاحظات والـ Feedback: {feedback}
        """
        
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}]
        )
        
        new_insight = response.choices[0].message.content
        
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
        # البحث عن التحليلات السابقة من DB و In-Memory
        past_db_insights = db.query(DBPerformanceInsight).filter(DBPerformanceInsight.employee_id == payload.employee_id).all()
        past_insights_texts = [f"Score: {item.performance_score}, Feedback: {item.feedback}" for item in past_db_insights]
        
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.ai_service.main:app", host="0.0.0.0", port=8000, reload=True)