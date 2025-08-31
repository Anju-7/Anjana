# app.py
import io
import math
import time
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import streamlit as st

# -----------------------------
# --------- CONFIG ------------
# -----------------------------
st.set_page_config(
    page_title="Classroom Monitoring – Skill Training",
    layout="wide",
    initial_sidebar_state="expanded",
)

PRIMARY_THRESHOLD_ENGAGEMENT = 0.60        # < 60% → alert
PRIMARY_THRESHOLD_PHONE_ABS = 5            # > 5 phones → alert
PRIMARY_THRESHOLD_PHONE_RATE = 0.20        # > 20% using phone → alert
PRIMARY_MIN_STUDENTS = 8                   # very low attendance → alert
PRIMARY_MIN_TEACHER_PRESENCE = True        # teacher must be present

# -----------------------------
# ------- HELPERS -------------
# -----------------------------
def coerce_bool(x):
    if isinstance(x, (bool, np.bool_)):
        return bool(x)
    if isinstance(x, (int, float)):
        return bool(int(x))
    s = str(x).strip().lower()
    return s in {"1", "y", "yes", "true", "present", "t", "p"}

def safe_div(a, b):
    return 0.0 if (b is None or b == 0 or pd.isna(b)) else a / b

def compute_engagement(row):
    """
    Engagement = max(0, min(1, (attentive / students) * bonus - penalty))
    but keep it simple and explainable.
    """
    students = max(0, int(row.get("students_present", 0) or 0))
    att = max(0, int(row.get("attentive_students", 0) or 0))
    distracted = max(0, int(row.get("distracted_students", 0) or 0))
    phones = max(0, int(row.get("phone_usage", 0) or 0))

    base = safe_div(att, students)  # 0..1
    # small penalty for phones and distraction
    penalty = 0.0
    if students > 0:
        penalty += 0.15 * safe_div(phones, students)
        penalty += 0.10 * safe_div(distracted, students)

    score = max(0.0, min(1.0, base - penalty))
    return score

def classify_alert(row):
    """
    Produce categorical judgement and a numeric risk score for sorting.
    """
    teacher_present = coerce_bool(row.get("teacher_present", False))
    students = int(row.get("students_present", 0) or 0)
    phones = int(row.get("phone_usage", 0) or 0)
    engagement = float(row.get("engagement_score", 0.0) or 0.0)

    issues = []

    # Teacher presence
    if PRIMARY_MIN_TEACHER_PRESENCE and not teacher_present:
        issues.append(("Teacher absent", 0.50))  # heavy weight

    # Low attendance (relative problem)
    if students < PRIMARY_MIN_STUDENTS:
        issues.append(("Low attendance", 0.20))

    # Phones (absolute or rate)
    phone_rate = safe_div(phones, max(1, students))
    if phones > PRIMARY_THRESHOLD_PHONE_ABS or phone_rate > PRIMARY_THRESHOLD_PHONE_RATE:
        issues.append(("High phone usage", 0.20))

    # Engagement
    if engagement < PRIMARY_THRESHOLD_ENGAGEMENT:
        # scale weight by how far below threshold
        gap = PRIMARY_THRESHOLD_ENGAGEMENT - engagement  # 0..1
        weight = min(0.40, 0.15 + 0.6 * gap)  # at least some weight
        issues.append(("Low engagement", weight))

    # Aggregate risk score (0..1)
    risk = 1 - np.prod([1 - w for _, w in issues]) if issues else 0.0

    # Map to traffic light
    if risk >= 0.55:
        level = "RED – Critical"
    elif risk >= 0.30:
        level = "YELLOW – Needs Monitoring"
    else:
        level = "GREEN – Good"

    reasons = [i for i, _ in issues] if issues else ["OK"]
    return level, float(risk), reasons

def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    # Standardize column names
    df = df.copy()
    df.columns = [c.strip().lower() for c in df.columns]

    # Expected minimal schema (case-insensitive):
    # session_id, institution_id, date_time (or date), teacher_present,
    # students_present, attentive_students, distracted_students, phone_usage
    # Optional: whiteboard_usage, practical_activity, engagement_score

    # Backward compatible aliases
    alias_map = {
        "datetime": "date_time",
        "date": "date_time",
        "teacher": "teacher_present",
        "phones": "phone_usage",
        "attentive": "attentive_students",
        "distracted": "distracted_students",
        "students": "students_present",
    }
    for a, b in alias_map.items():
        if a in df.columns and b not in df.columns:
            df[b] = df[a]

    # Fill essentials if missing
    if "session_id" not in df.columns:
        df["session_id"] = [f"S{str(i+1).zfill(3)}" for i in range(len(df))]
    if "institution_id" not in df.columns:
        df["institution_id"] = "UNKNOWN"

    # Date/time parsing
    if "date_time" in df.columns:
        df["date_time"] = pd.to_datetime(df["date_time"], errors="coerce")
    else:
        df["date_time"] = pd.to_datetime(datetime.now())

    # Coerce numeric fields
    for col in ["students_present", "attentive_students", "distracted_students", "phone_usage", "whiteboard_usage", "practical_activity"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
        else:
            df[col] = 0

    # Booleans
    if "teacher_present" in df.columns:
        df["teacher_present"] = df["teacher_present"].map(coerce_bool)
    else:
        df["teacher_present"] = False

    # Engagement
    if "engagement_score" in df.columns:
        # If provided, trust but clip
        df["engagement_score"] = pd.to_numeric(df["engagement_score"], errors="coerce").fillna(0.0).clip(0, 1)
    else:
        df["engagement_score"] = df.apply(compute_engagement, axis=1)

    # Derived rates
    df["phone_rate"] = df.apply(lambda r: safe_div(r["phone_usage"], max(1, r["students_present"])), axis=1)

    # Classify
    results = df.apply(lambda r: classify_alert(r), axis=1)
    df["alert_level"] = [r[0] for r in results]
    df["risk_score"] = [round(r[1], 3) for r in results]
    df["alert_reasons"] = [", ".join(r[2]) for r in results]
    return df

def generate_sample_data(n_sessions=60, n_institutions=5, start_days_ago=7):
    rng = np.random.default_rng(42)
    rows = []
    start_date = datetime.now() - timedelta(days=start_days_ago)

    for i in range(n_sessions):
        inst = f"INST_{1 + (i % n_institutions):02d}"
        dt = start_date + timedelta(minutes=60 * i // max(1, n_institutions))
        students = int(rng.integers(4, 42))
        teacher_present = bool(rng.random() > 0.12)  # ~12% absent
        # attentive baseline
        attentive = int(max(0, rng.normal(loc=students * 0.72, scale=max(1, students * 0.12))))
        attentive = min(attentive, students)
        distracted = max(0, students - attentive)
        phones = int(max(0, rng.normal(loc=students * 0.10, scale=max(1, students * 0.06))))
        whiteboard = int(rng.integers(0, 2))  # 0/1
        practical = int(rng.integers(0, 2))   # 0/1

        row = dict(
            session_id=f"S{str(i+1).zfill(3)}",
            institution_id=inst,
            date_time=dt,
            teacher_present=teacher_present,
            students_present=students,
            attentive_students=attentive,
            distracted_students=distracted,
            phone_usage=phones,
            whiteboard_usage=whiteboard,
            practical_activity=practical,
        )
        rows.append(row)

    df = pd.DataFrame(rows)
    df["engagement_score"] = df.apply(compute_engagement, axis=1)
    # Reclassify to include engagement
    df = normalize_columns(df)
    return df

def to_excel_bytes(dfs: dict):
    import io
    from openpyxl import Workbook
    from openpyxl.utils.dataframe import dataframe_to_rows

    output = io.BytesIO()
    wb = Workbook()
    wb.remove(wb.active)

    for sheet_name, df in dfs.items():
        ws = wb.create_sheet(title=sheet_name[:31])  # Excel sheet name limit

        for r in dataframe_to_rows(df, index=False, header=True):
            ws.append(r)

        # Adjust column widths safely
        for i, col in enumerate(df.columns, 1):
            col_lengths = df[col].dropna().astype(str).str.len()
            if len(col_lengths) > 0:
                width = min(40, max(12, int(col_lengths.quantile(0.9))))
            else:
                width = 12
            ws.column_dimensions[chr(64+i)].width = width

    wb.save(output)
    return output.getvalue()


# -----------------------------
# --------- SIDEBAR -----------
# -----------------------------
st.sidebar.title("🧭 Controls")

source = st.sidebar.radio(
    "Data Source",
    ["Upload CSV", "Use Sample Data"],
    help="Upload a CSV with session-level metrics or generate realistic sample data."
)

if source == "Upload CSV":
    uploaded = st.sidebar.file_uploader(
        "Upload CSV",
        type=["csv"],
        accept_multiple_files=False,
        help="Columns can include: session_id, institution_id, date_time, teacher_present, students_present, attentive_students, distracted_students, phone_usage, (optional) engagement_score."
    )
else:
    uploaded = None

# Threshold sliders (so you can demo 'policy tuning')
st.sidebar.subheader("Policy Thresholds")
PRIMARY_THRESHOLD_ENGAGEMENT = st.sidebar.slider("Min Engagement (Good)", 0.0, 1.0, PRIMARY_THRESHOLD_ENGAGEMENT, 0.01)
PRIMARY_THRESHOLD_PHONE_ABS = st.sidebar.number_input("Max Phones (absolute)", min_value=0, value=PRIMARY_THRESHOLD_PHONE_ABS, step=1)
PRIMARY_THRESHOLD_PHONE_RATE = st.sidebar.slider("Max Phones (% of class)", 0.0, 1.0, PRIMARY_THRESHOLD_PHONE_RATE, 0.01)
PRIMARY_MIN_STUDENTS = st.sidebar.number_input("Min Students (attendance)", min_value=0, value=PRIMARY_MIN_STUDENTS, step=1)

# -----------------------------
# --------- DATA --------------
# -----------------------------
if uploaded is not None:
    raw_df = pd.read_csv(uploaded)
    st.toast("CSV uploaded successfully.", icon="✅")
else:
    n_sess = st.sidebar.slider("Sample sessions", 20, 200, 80, 10)
    n_inst = st.sidebar.slider("Institutions", 1, 20, 6, 1)
    days = st.sidebar.slider("Days covered (approx.)", 1, 30, 7, 1)
    raw_df = generate_sample_data(n_sessions=n_sess, n_institutions=n_inst, start_days_ago=days)

# Recompute now that sliders may have changed globals
# (We reuse classify_alert thresholds set above.)
df = normalize_columns(raw_df)


# -----------------------------
# --------- HEADER ------------
# -----------------------------
st.title("📊 Monitoring System for Classroom Sessions – Skill Training")
st.caption("Prototype: CSV-based classroom monitoring with automated flagging (SIH-ready MVP).")

# --- KPI SUMMARY CARDS ---
st.subheader("📊 Overall Monitoring Summary")

total_sessions = len(df)
good_sessions = (df["alert_level"].str.startswith("GREEN")).mean() * 100
needs_monitoring = (df["alert_level"].str.startswith("YELLOW")).mean() * 100
critical = (df["alert_level"].str.startswith("RED")).mean() * 100

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown(f"""
    <div style="background-color:#f0f2f6;padding:20px;border-radius:12px;text-align:center;">
        <h3>{total_sessions}</h3>
        <p>Total Sessions</p>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div style="background-color:#d4edda;padding:20px;border-radius:12px;text-align:center;">
        <h3>{good_sessions:.1f}%</h3>
        <p>Good Sessions</p>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown(f"""
    <div style="background-color:#fff3cd;padding:20px;border-radius:12px;text-align:center;">
        <h3>{needs_monitoring:.1f}%</h3>
        <p>Needs Monitoring</p>
    </div>
    """, unsafe_allow_html=True)

with col4:
    st.markdown(f"""
    <div style="background-color:#f8d7da;padding:20px;border-radius:12px;text-align:center;">
        <h3>{critical:.1f}%</h3>
        <p>Critical</p>
    </div>
    """, unsafe_allow_html=True)

# -----------------------------
# ---- FILTERS & TABLE --------
# -----------------------------
colF1, colF2, colF3 = st.columns([1, 1, 1])
with colF1:
    inst_filter = st.multiselect(
        "Filter by Institution",
        sorted(df["institution_id"].astype(str).unique()),
        default=None
    )
with colF2:
    level_filter = st.multiselect(
        "Filter by Alert Level",
        ["GREEN – Good", "YELLOW – Needs Monitoring", "RED – Critical"],
        default=None
    )
with colF3:
    date_min = df["date_time"].min()
    date_max = df["date_time"].max()
    date_range = st.date_input(
        "Date Range",
        value=(date_min.date(), date_max.date()),
        min_value=date_min.date(),
        max_value=date_max.date()
    )

fdf = df.copy()
if inst_filter:
    fdf = fdf[fdf["institution_id"].isin(inst_filter)]
if level_filter:
    fdf = fdf[fdf["alert_level"].isin(level_filter)]
if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    start_d = pd.to_datetime(date_range[0])
    end_d = pd.to_datetime(date_range[1]) + pd.Timedelta(days=1)
    fdf = fdf[(fdf["date_time"] >= start_d) & (fdf["date_time"] < end_d)]

# Sort by risk
fdf = fdf.sort_values(by=["risk_score", "date_time"], ascending=[False, False]).reset_index(drop=True)

st.subheader("Session-Level Monitoring")
st.dataframe(
    fdf[[
        "session_id", "institution_id", "date_time",
        "teacher_present", "students_present", "attentive_students",
        "distracted_students", "phone_usage", "engagement_score",
        "alert_level", "risk_score", "alert_reasons"
    ]].style.format({
        "engagement_score": "{:.0%}",
        "risk_score": "{:.0%}",
        "phone_rate": "{:.0%}",
    }),
    use_container_width=True,
    hide_index=True
)

# -----------------------------
# -------- CHARTS -------------
# -----------------------------
st.markdown("### Trends & Aggregates")

c1, c2 = st.columns(2)

with c1:
    st.markdown("**Engagement by Institution** (median)")
    inst_eng = fdf.groupby("institution_id")["engagement_score"].median().sort_values(ascending=False)
    st.bar_chart(inst_eng)

with c2:
    st.markdown("**Alert Mix by Institution**")
    mix = pd.crosstab(fdf["institution_id"], fdf["alert_level"], normalize="index").fillna(0).sort_index()
    st.bar_chart(mix)

st.markdown("**Daily Engagement Trend (median)**")
daily = fdf.copy()
daily["date"] = daily["date_time"].dt.date
daily_eng = daily.groupby("date")["engagement_score"].median()
st.line_chart(daily_eng)

# -----------------------------
# ---- EXPORTS / REPORTS ------
# -----------------------------
st.markdown("---")
st.subheader("Export Reports")

flagged = fdf[fdf["alert_level"].str.startswith(("RED", "YELLOW"))].copy()
by_institution = fdf.groupby("institution_id").agg(
    sessions=("session_id", "count"),
    median_engagement=("engagement_score", "median"),
    pct_critical=("alert_level", lambda s: (s.str.startswith("RED")).mean()),
    pct_monitor=("alert_level", lambda s: (s.str.startswith("YELLOW")).mean()),
    pct_good=("alert_level", lambda s: (s.str.startswith("GREEN")).mean()),
).reset_index()

colE1, colE2, colE3 = st.columns(3)
with colE1:
    st.caption("Flagged Sessions (YELLOW/RED)")
    st.dataframe(flagged[[
        "session_id", "institution_id", "date_time",
        "teacher_present", "students_present",
        "phone_usage", "engagement_score", "alert_level", "risk_score", "alert_reasons"
    ]], use_container_width=True, hide_index=True)
with colE2:
    st.caption("Institution Summary")
    st.dataframe(by_institution.style.format({
        "median_engagement": "{:.0%}",
        "pct_critical": "{:.0%}",
        "pct_monitor": "{:.0%}",
        "pct_good": "{:.0%}",
    }), use_container_width=True, hide_index=True)
with colE3:
    st.info("Download consolidated Excel with multiple sheets:")
    excel_bytes = to_excel_bytes({
        "All Sessions": fdf,
        "Flagged Sessions": flagged,
        "Institution Summary": by_institution,
    })
    st.download_button(
        label="⬇️ Download Monitoring Report (.xlsx)",
        data=excel_bytes,
        file_name=f"classroom_monitoring_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )

st.markdown("---")
with st.expander("📄 CSV Template (copy/paste to build your own data)"):
    template = pd.DataFrame({
        "session_id": ["S001", "S002"],
        "institution_id": ["INST_01", "INST_01"],
        "date_time": [datetime.now().strftime("%Y-%m-%d %H:%M"), (datetime.now()-timedelta(hours=2)).strftime("%Y-%m-%d %H:%M")],
        "teacher_present": ["Yes", "No"],
        "students_present": [25, 12],
        "attentive_students": [18, 4],
        "distracted_students": [7, 8],
        "phone_usage": [3, 6],
        # optional: "engagement_score": [0.72, 0.31],
        "whiteboard_usage": [1, 0],
        "practical_activity": [0, 0],
    })
    st.dataframe(template, use_container_width=True, hide_index=True)
    st.caption("Save as CSV and upload above.")
