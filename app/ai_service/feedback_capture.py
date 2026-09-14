"""
AI Feedback Capture
--------------------
يسجل تقييم المستخدمين على مخرجات الـ AI (useful / not_useful) بصيغة JSON
منظمة تطابق الـ Input Schema المتفق عليه، ويحسب نسبة "not_useful" لكل
insight_type عشان نعرف مين محتاج مراجعة (Usage Logic).
"""

import json
import os
from datetime import datetime, timezone

FEEDBACK_FILE = "feedback.json"

VALID_INSIGHT_TYPES = [
    "policy_answer",
    "evaluation_draft",
    "career_coach",
    "performance_insight",
    "attention_signal",
]
VALID_ROLES = ["employee", "manager", "hr"]
VALID_RATINGS = ["useful", "not_useful"]

NOT_USEFUL_ALERT_THRESHOLD = 0.20  # 20% زي المتفق عليه في التوثيق


def load_feedback():
    """تحميل كل السجلات الموجودة، أو قايمة فاضية لو الملف مش موجود."""
    if not os.path.exists(FEEDBACK_FILE):
        return []
    with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []

def save_feedback(records):
    directory = os.path.dirname(FEEDBACK_FILE)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(FEEDBACK_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

def capture_feedback(insight_id, insight_type, user_id, user_role, rating,
                      flagged_for_review=False, comment=None):
    """
    يسجل تقييم جديد مطابق للـ Input Schema.
    لو نفس اليوزر قيّم نفس الـ insight قبل كده، بيعدّل التقييم بدل ما يكرره.
    """
    if insight_type not in VALID_INSIGHT_TYPES:
        raise ValueError(f"insight_type غير معروف: {insight_type}")
    if user_role not in VALID_ROLES:
        raise ValueError(f"user_role غير معروف: {user_role}")
    if rating not in VALID_RATINGS:
        raise ValueError(f"rating لازم يكون useful أو not_useful")

    records = load_feedback()

    # امنع تكرار نفس التقييم من نفس اليوزر لنفس الـ insight — عدّل بدل ما يضيف سجل جديد
    for record in records:
        if record["insight_id"] == insight_id and record["user_id"] == user_id:
            record.update({
                "rating": rating,
                "flagged_for_review": flagged_for_review,
                "comment": comment,
                "submitted_at": datetime.now(timezone.utc).isoformat(),
            })
            save_feedback(records)
            return record

    new_record = {
        "insight_id": insight_id,
        "insight_type": insight_type,
        "user_id": user_id,
        "user_role": user_role,
        "rating": rating,
        "flagged_for_review": flagged_for_review,
        "comment": comment,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
    }
    records.append(new_record)
    save_feedback(records)
    return new_record


def analyze_feedback():
    """
    يحسب نسبة not_useful لكل insight_type، ويحدد أي نوع محتاج مراجعة
    (زي ما اتفقنا في الـ Usage Logic بالتوثيق).
    """
    records = load_feedback()
    stats = {}

    for r in records:
        t = r["insight_type"]
        stats.setdefault(t, {"useful": 0, "not_useful": 0, "flagged": 0})
        stats[t][r["rating"]] += 1
        if r.get("flagged_for_review"):
            stats[t]["flagged"] += 1

    report = []
    for insight_type, counts in stats.items():
        total = counts["useful"] + counts["not_useful"]
        not_useful_ratio = counts["not_useful"] / total if total else 0
        needs_review = not_useful_ratio > NOT_USEFUL_ALERT_THRESHOLD
        report.append({
            "insight_type": insight_type,
            "total_ratings": total,
            "not_useful_ratio": round(not_useful_ratio, 2),
            "flagged_count": counts["flagged"],
            "needs_review": needs_review,
        })
    return report


def print_analysis():
    report = analyze_feedback()
    if not report:
        print("مفيش تقييمات مسجلة لسه.")
        return
    print("\n--- تقرير جودة الـ AI ---")
    for row in report:
        flag = "⚠️ يحتاج مراجعة" if row["needs_review"] else "✅ سليم"
        print(
            f"{row['insight_type']}: "
            f"{row['total_ratings']} تقييم | "
            f"not_useful = {row['not_useful_ratio']*100:.0f}% | "
            f"flagged = {row['flagged_count']} | {flag}"
        )


def run_demo():
    """ديمو بسيط في التيرمينال لاختبار الفكرة."""
    print("=== AI Feedback Capture — Demo ===\n")

    insight_id = input("insight_id (مثلاً abc-123): ").strip()
    print("أنواع الـ insight المتاحة:", ", ".join(VALID_INSIGHT_TYPES))
    insight_type = input("insight_type: ").strip()

    user_id = input("user_id: ").strip()
    print("الأدوار المتاحة:", ", ".join(VALID_ROLES))
    user_role = input("user_role: ").strip()

    print("التقييم: 1) useful   2) not_useful")
    choice = input("اختر (1/2): ").strip()
    rating = "useful" if choice == "1" else "not_useful"

    flagged = input("الإبلاغ عن مشكلة في الرد؟ (y/n): ").strip().lower() == "y"
    comment = input("تعليق (اختياري، اضغط Enter للتخطي): ").strip() or None

    try:
        record = capture_feedback(
            insight_id, insight_type, user_id, user_role,
            rating, flagged, comment
        )
        print("\n✅ تم تسجيل الـ Feedback بنجاح:")
        print(json.dumps(record, ensure_ascii=False, indent=2))
    except ValueError as e:
        print(f"\n❌ خطأ: {e}")
        return

    print_analysis()


if __name__ == "__main__":
    run_demo()