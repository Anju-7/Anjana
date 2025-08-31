# analyzer_utils.py

from .logger_utils import log_event

def analyze_session(row):
    """
    Very basic rule: Good / Needs Monitoring / Critical
    Can be extended.
    """
    if row["teacher_present"] is False:
        status = "Critical"
    elif row["attentive_students"] < row["students_present"] * 0.5:
        status = "Needs Monitoring"
    else:
        status = "Good"

    # log session analysis
    log_event("SESSION_ANALYZED", {
        "session_id": row.get("session_id"),
        "institution_id": row.get("institution_id"),
        "status": status
    })
    return status
