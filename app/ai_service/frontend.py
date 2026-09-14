import streamlit as st
import requests
import pandas as pd

import tempfile
import io
import os

API_URL = "http://127.0.0.1:8000"

st.set_page_config(page_title="Smart HR - AI Analytics", page_icon="📊", layout="wide")

TRANSLATIONS = {
    "ar": {
        "title": "📊 نظام إدارة الموارد البشرية الذكي - تحليلات الذكاء الاصطناعي",
        "sidebar_header": "لوحة التحكم",
        "system_status": "حالة النظام",
        "server_connected": "🟢 الخادم متصل ويعمل بنجاح",
        "server_unstable": "🟡 الخادم يستجيب ولكن بحالة غير متوقعة",
        "server_disconnected": "🔴 غير متصل بالخادم (تأكد من تشغيل FastAPI)",
        "choose_service": "اختر الخدمة:",
        "login": "تسجيل الدخول",
        "register_users": "تسجيل المستخدمين",
        "policy_assistant": "مساعد سياسات",
        "exec_dashboard": "لوحة الإدارة العليا",
        "smart_alerts": "التنبيهات والتوصيات الذكية",
        "performance_insight": "رؤى الأداء",
        "evaluation_draft": "مسودة التقييم",
        "employee_360": "ملف الموظف الشامل",
        "history_records": "سجلات التاريخ",
        "analytics_feedback": "تقييم التحليلات",
        "visual_dashboard": "لوحة المؤشرات البيانية",
        "batch_evaluation": "المعالجة الجماعية للتقييمات"
    },
    "en": {
        "title": "📊 Smart HR Management System - AI Analytics",
        "sidebar_header": "Control Panel",
        "system_status": "System Status",
        "server_connected": "🟢 Server connected and running successfully",
        "server_unstable": "🟡 Server responding with unexpected status",
        "server_disconnected": "🔴 Server disconnected (Make sure FastAPI is running)",
        "choose_service": "Choose Service:",
        "login": "Login",
        "register_users": "Register Users",
        "policy_assistant": "Policy Assistant",
        "exec_dashboard": "Executive Dashboard",
        "smart_alerts": "Smart Alerts & Recommendations",
        "performance_insight": "Performance Insights",
        "evaluation_draft": "Evaluation Draft",
        "employee_360": "Employee 360° Profile",
        "history_records": "History Records",
        "analytics_feedback": "Analytics Feedback",
        "visual_dashboard": "Visual Dashboard",
        "batch_evaluation": "Batch Evaluation Processing"
    }
}

if "lang" not in st.session_state:
    st.session_state["lang"] = "ar"

lang_choice = st.sidebar.selectbox("Language / اللغة", ["العربية", "English"])
if lang_choice == "English":
    st.session_state["lang"] = "en"
else:
    st.session_state["lang"] = "ar"

t = TRANSLATIONS[st.session_state["lang"]]

st.title(t["title"])
st.sidebar.header(t["sidebar_header"])

st.sidebar.markdown("---")
st.sidebar.subheader(t["system_status"])
try:
    health_res = requests.get(f"{API_URL}/")
    if health_res.status_code == 200:
        st.sidebar.success(t["server_connected"])
    else:
        st.sidebar.warning(t["server_unstable"])
except requests.exceptions.ConnectionError:
    st.sidebar.error(t["server_disconnected"])
st.sidebar.markdown("---")

if "token" not in st.session_state:
    st.session_state["token"] = None
if "user_role" not in st.session_state:
    st.session_state["user_role"] = "guest"

menu_options = [t["login"], t["register_users"], t["policy_assistant"]]

if st.session_state["token"]:
    menu_options = [
        t["exec_dashboard"], 
        t["smart_alerts"], 
        t["performance_insight"], 
        t["policy_assistant"], 
        t["evaluation_draft"], 
        t["employee_360"], 
        t["history_records"], 
        t["analytics_feedback"], 
        t["visual_dashboard"],
        t["batch_evaluation"]
    ]
    if st.session_state.get("user_role") == "hr_admin":
        menu_options.append(t["register_users"])

choice = st.sidebar.selectbox(t["choose_service"], menu_options)

if choice == t["login"]:
    st.subheader("تسجيل الدخول إلى النظام / Login")
    username = st.text_input("اسم المستخدم / Username")
    password = st.text_input("كلمة المرور / Password", type="password")
    
    if st.button("تسجيل الدخول"):
        response = requests.post(f"{API_URL}/token", data={"username": username, "password": password})
        if response.status_code == 200:
            token_data = response.json()
            st.session_state["token"] = token_data.get("access_token")
            st.session_state["user_role"] = token_data.get("role", "manager")
            st.success("تم تسجيل الدخول بنجاح!")
        else:
            st.error("فشل تسجيل الدخول، تأكد من البيانات.")

elif choice == t["register_users"]:
    st.subheader("إنشاء حساب جديد في النظام")
    new_username = st.text_input("اسم المستخدم الجديد")
    new_password = st.text_input("كلمة المرور", type="password")
    role = st.selectbox("الدور الوظيفي", ["manager", "hr_admin", "employee"])
    
    if st.button("تسجيل الحساب"):
        payload = {"username": new_username, "password": new_password, "role": role}
        res = requests.post(f"{API_URL}/register", json=payload)
        if res.status_code == 200:
            st.success("تم تسجيل المستخدم بنجاح!")
        else:
            st.error(f"خطأ: {res.text}")

headers = {"Authorization": f"Bearer {st.session_state['token']}"} if st.session_state["token"] else {}

if choice == t["exec_dashboard"]:
    st.subheader("📈 لوحة الإدارة العليا (Executive Dashboard)")
    res = requests.get(f"{API_URL}/ai/history", headers=headers)
    if res.status_code == 200:
        result = res.json()
        history_list = result.get("history", [])
        if history_list:
            scores = [float(item.get("overall_score") or item.get("score")) for item in history_list if (item.get("overall_score") or item.get("score")) is not None]
            total_reports = len(history_list)
            avg_score = sum(scores) / len(scores) if scores else 0.0
            
            col1, col2, col3 = st.columns(3)
            with col1: st.metric(label="إجمالي التقارير", value=total_reports)
            with col2: st.metric(label="متوسط الأداء", value=f"{avg_score:.2f}%")
            with col3: st.metric(label="حالة النظام", value="مستقر 🟢")
            
            st.markdown("---")
            st.bar_chart(data=scores)
            
            df_exec = pd.DataFrame(history_list)
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_exec.to_excel(writer, sheet_name='Executive Summary', index=False)
            
            st.download_button(
                label="📥 تنزيل الملخص التنفيذي بصيغة Excel (XLSX)",
                data=output.getvalue(),
                file_name="Executive_Summary.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.info("لا توجد بيانات كافية.")
    else:
        st.error("فشل جلب البيانات.")

elif choice == t["smart_alerts"]:
    st.subheader("🚨 نظام التنبيهات والتوصيات الذكية الآلية")
    threshold = st.slider("حدد حد التنبيه لدرجة الأداء (%)", min_value=50, max_value=90, value=75)
    res = requests.get(f"{API_URL}/ai/history", headers=headers)
    if res.status_code == 200:
        history_list = res.json().get("history", [])
        low_performers = [item for item in history_list if (item.get("overall_score") or item.get("score")) is not None and float(item.get("overall_score") or item.get("score")) < threshold]
        if low_performers:
            st.warning(f"⚠️ تنبيه: تم العثور على {len(low_performers)} سجلات بأداء أقل من {threshold}%")
            for alert in low_performers:
                st.error(f"الموظف: **{alert.get('employee_id')}** | الدرجة: **{alert.get('overall_score') or alert.get('score')}%** | التوصية: جدولة اجتماع توجيه وتدريب عاجل.")
        else:
            st.success("🟢 لا توجد حالات حرجة مسجلة.")

elif choice == t["performance_insight"]:
    st.subheader("تحليل أداء الموظف بالذكاء الاصطناعي")
    employee_id = st.text_input("رقم الموظف", value="EMP-101")
    performance_score = st.number_input("درجة الأداء", min_value=0.0, max_value=100.0, value=85.0)
    tasks_completed = st.number_input("المهام المنجزة", min_value=0, value=40)
    feedback = st.text_area("ملاحظات الأداء", value="أدى المهام بكفاءة عالية.")
    
    if st.button("تشغيل التحليل"):
        payload = {"employee_id": employee_id, "performance_score": performance_score, "tasks_completed": tasks_completed, "feedback": feedback}
        res = requests.post(f"{API_URL}/ai/performance-insight", json=payload, headers=headers)
        if res.status_code == 200:
            data = res.json()
            st.success(data.get('status'))
            st.info(data.get('insight'))

elif choice == t["policy_assistant"]:
    st.subheader("مساعد سياسات الموارد البشرية (RAG)")
    
    uploaded_pdf = st.file_uploader("رفع ملف سياسة الشركة (PDF)", type=["pdf"])
    if uploaded_pdf is not None:
        if st.button("رفع وفهرسة المستند"):
            files = {"file": (uploaded_pdf.name, uploaded_pdf.getvalue(), "application/pdf")}
            res = requests.post(f"{API_URL}/ai/upload-policy-pdf", files=files, headers=headers)
            if res.status_code == 200:
                st.success(f"تم رفع وفهرسة الملف بنجاح! عدد الأجزاء المفهرسة: {res.json().get('chunks_indexed')}")
            else:
                st.error("فشل رفع الملف أو الفهرسة.")

    st.markdown("---")
    employee_id = st.text_input("رقم الموظف", value="EMP-101")
    question = st.text_input("اكتب سؤالك حول سياسات الشركة", value="ما هي سياسة الإجازات؟")
    if st.button("إرسال السؤال"):
        res = requests.post(f"{API_URL}/ai/policy-assistant", json={"employee_id": employee_id, "question": question})
        if res.status_code == 200:
            st.write(res.json().get("answer"))

elif choice == t["evaluation_draft"]:
    st.subheader("توليد مسودة تقييم الأداء")
    employee_id = st.text_input("رقم الموظف", value="EMP-101")
    evaluation_period = st.text_input("فترة التقييم", value="Q3 2026")
    goals_met = st.checkbox("هل تم تحقيق الأهداف؟", value=True)
    manager_notes = st.text_area("ملاحظات المدير", value="أظهر التزاماً ممتازاً.")
    if st.button("توليد المسودة"):
        res = requests.post(f"{API_URL}/ai/evaluation-draft", json={"employee_id": employee_id, "evaluation_period": evaluation_period, "goals_met": goals_met, "manager_notes": manager_notes}, headers=headers)
        if res.status_code == 200:
            st.markdown(res.json().get("evaluation_draft"))

elif choice == t["employee_360"]:
    st.subheader("📁 ملف الموظف الشامل ومقارنة الاتجاه التاريخي")
    target_emp = st.text_input("أدخل رقم الموظف للبحث", value="EMP-101")
    if st.button("عرض الملف الشامل"):
        res = requests.get(f"{API_URL}/ai/history", headers=headers)
        if res.status_code == 200:
            emp_records = [item for item in res.json().get("history", []) if target_emp.lower() in str(item.get("employee_id", "")).lower()]
            if emp_records:
                emp_scores = [float(item.get("overall_score") or item.get("score")) for item in emp_records if (item.get("overall_score") or item.get("score")) is not None]
                if emp_scores:
                    st.metric(label="متوسط درجة الأداء", value=f"{sum(emp_scores)/len(emp_scores):.2f}%")
                    st.line_chart(emp_scores)
                st.json(emp_records)
            else:
                st.warning("لا توجد سجلات لهذا الموظف.")

elif choice == t["history_records"]:
    st.subheader("سجل التحليلات السابقة وتصدير Excel")
    if st.button("جلب السجل"):
        res = requests.get(f"{API_URL}/ai/history", headers=headers)
        if res.status_code == 200:
            history_list = res.json().get("history", [])
            st.json(history_list)
            if history_list:
                df = pd.DataFrame(history_list)
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df.to_excel(writer, sheet_name='History Records', index=False)
                st.download_button(
                    label="📥 تحميل السجل بصيغة Excel (XLSX)",
                    data=output.getvalue(),
                    file_name="HR_History_Records.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

elif choice == t["analytics_feedback"]:
    st.subheader("تقييم وتحسين مخرجات الذكاء الاصطناعي")
    insight_id = st.text_input("معرف التحليل", value="INSIGHT-EMP-101-1")
    insight_type = st.selectbox("نوع التحليل", ["performance_insight", "evaluation_draft"])
    rating = st.selectbox("التقييم", ["useful", "not_useful"])
    comment = st.text_area("تعليق إضافي", value="ممتاز ودقيق.")
    if st.button("إرسال التقييم"):
        payload = {"insight_id": insight_id, "insight_type": insight_type, "user_id": "manager_1", "user_role": "manager", "rating": rating, "flagged_for_review": False, "comment": comment}
        res = requests.post(f"{API_URL}/ai/feedback", json=payload)
        if res.status_code == 200:
            st.success("تم إرسال التقييم بنجاح!")

elif choice == t["visual_dashboard"]:
    st.subheader("لوحة المؤشرات والتحليلات البصرية")
    res = requests.get(f"{API_URL}/ai/history", headers=headers)
    if res.status_code == 200:
        scores = [float(item.get("overall_score") or item.get("score")) for item in res.json().get("history", []) if (item.get("overall_score") or item.get("score")) is not None]
        if scores:
            st.bar_chart(data=scores)
        else:
            st.info("لا توجد بيانات كافية.")

elif choice == t["batch_evaluation"]:
    st.subheader("⚡ المعالجة الجماعية لتقييم الموظفين (Batch Processing)")
    st.write("قم برفع ملف CSV يحتوي على أعمدة: `employee_id`, `performance_score`, `tasks_completed`, `feedback` لتسجيل وتقييم عدة موظفين دفعة واحدة.")
    
    uploaded_file = st.file_uploader("اختر ملف CSV", type=["csv"])
    if uploaded_file is not None:
        df_batch = pd.read_csv(uploaded_file)
        st.write("معاينة البيانات المرفوعة:", df_batch.head())
        
        if st.button("تنفيذ المعالجة الجماعية"):
            success_count = 0
            for index, row in df_batch.iterrows():
                payload = {
                    "employee_id": str(row.get("employee_id", f"EMP-BATCH-{index}")),
                    "performance_score": float(row.get("performance_score", 80.0)),
                    "tasks_completed": int(row.get("tasks_completed", 30)),
                    "feedback": str(row.get("feedback", "تقييم جماعي آلي"))
                }
                res = requests.post(f"{API_URL}/ai/performance-insight", json=payload, headers=headers)
                if res.status_code == 200:
                    success_count += 1
            st.success(f"تم معالجة وإضافة {success_count} موظف بنجاح إلى قاعدة البيانات!")