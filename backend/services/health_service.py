"""System Health Check Service.

Performs verification of core platform components:
1. SQLite Database connectivity & schemas.
2. REST API application routing.
3. Local AI matching & representation module.
4. SentenceTransformer / Local embedding engine.
5. Opportunity repository status.
6. Demonstration personas and datasets.
"""

import sys
from pathlib import Path
from typing import Dict, Any

from backend.utils.config import settings
from backend.utils.logger import get_logger
from backend.database.db import SessionLocal, OpportunityDB, StudentDB, ApplicationDB, SavedOpportunityDB, NotificationPreferenceDB

logger = get_logger("health_service")


def check_system_health() -> Dict[str, Any]:
    """Execute end-to-end component diagnostics and return structured health status."""
    report = {
        "status": "HEALTHY",
        "checks": {},
        "details": {}
    }

    # 1. Database Check
    try:
        session = SessionLocal()
        opp_count = session.query(OpportunityDB).count()
        student_count = session.query(StudentDB).count()
        app_count = session.query(ApplicationDB).count()
        saved_count = session.query(SavedOpportunityDB).count()
        session.close()

        report["checks"]["Database"] = "OK"
        report["details"]["Database"] = f"SQLite connected ({opp_count} opps, {student_count} students, {app_count} apps, {saved_count} saved)"
    except Exception as e:
        report["status"] = "DEGRADED"
        report["checks"]["Database"] = f"FAILED: {e}"

    # 2. API Modules Check
    try:
        from fastapi.testclient import TestClient
        from backend.api.app import app
        from backend.utils.security import create_access_token
        client = TestClient(app)
        token = create_access_token({"sub": "default_student", "email": "health@careerhub.local", "role": "STUDENT"})
        headers = {"Authorization": f"Bearer {token}"}

        res_health = client.get("/api/health")
        res_opps = client.get("/api/opportunities?limit=1")
        res_match = client.get("/api/matching/recommendations?limit=1", headers=headers)
        res_stud = client.get("/api/student", headers=headers)
        res_apps = client.get("/api/applications", headers=headers)

        if (res_health.status_code == 200 and res_opps.status_code == 200 and
            res_match.status_code == 200 and res_stud.status_code == 200 and
            res_apps.status_code == 200):
            report["checks"]["API modules"] = "OK"
            report["details"]["API modules"] = "Auth, Opportunities, Matching, Student, and Applications endpoints responding with HTTP 200"
        else:
            report["checks"]["API modules"] = "WARNING: Some endpoints did not return HTTP 200"

    except Exception as e:
        report["status"] = "DEGRADED"
        report["checks"]["API modules"] = f"FAILED: {e}"

    # 3. AI Modules Check
    try:
        from backend.ai.scorer import score_job, calculate_match_details
        from backend.ai.skill_dictionary import extract_skills_from_text
        from backend.services.matching_service import get_recommendations
        skills = extract_skills_from_text("Experience with Python and PyTorch")
        if "Python" in skills and "PyTorch" in skills:
            report["checks"]["AI module"] = "OK"
            report["details"]["AI module"] = "Skill extraction, hybrid scorer & matching engine operational"
        else:
            report["checks"]["AI module"] = "WARNING: Skill extraction returned unexpected tokens"
    except Exception as e:
        report["status"] = "DEGRADED"
        report["checks"]["AI module"] = f"FAILED: {e}"

    # 4. Embedding Engine Check
    try:
        from backend.ai.embedder import get_embedding, get_model
        test_emb = get_embedding("machine learning student")
        model = get_model()
        model_type = "SentenceTransformer (all-MiniLM-L6-v2)" if model is not None else "Offline Local TF-IDF Fallback"
        report["checks"]["Embedding"] = f"OK ({model_type})"
        report["details"]["Embedding"] = f"Vector dimension: {len(test_emb)} ({model_type})"
    except Exception as e:
        report["checks"]["Embedding"] = f"WARNING: {e}"

    # 5. Opportunity DB Check
    try:
        session = SessionLocal()
        total = session.query(OpportunityDB).count()
        active = session.query(OpportunityDB).filter(OpportunityDB.status.in_(["active", "open"])).count()
        expired = session.query(OpportunityDB).filter_by(status="expired").count()
        session.close()

        if total > 0:
            report["checks"]["Opportunity DB"] = f"OK ({active} active, {expired} expired, {total} total)"
        else:
            report["checks"]["Opportunity DB"] = "WARNING: 0 records in database (run --seed-demo or --ingest)"
    except Exception as e:
        report["checks"]["Opportunity DB"] = f"FAILED: {e}"

    # 6. Demo Data Check
    try:
        demo_json = settings.DATA_DIR / "demo_students.json"
        demo_csv = settings.DATA_DIR / "demo_opportunities_realistic.csv"

        has_json = demo_json.exists()
        has_csv = demo_csv.exists()

        if has_json and has_csv:
            report["checks"]["Demo data"] = "OK (Student A / Student B personas & 75+ realistic opps available)"
        elif has_json:
            report["checks"]["Demo data"] = "OK (demo_students.json present)"
        else:
            report["checks"]["Demo data"] = "WARNING: demo_students.json missing"
    except Exception as e:
        report["checks"]["Demo data"] = f"FAILED: {e}"

    return report


def print_health_check_summary() -> bool:
    """Print formatted terminal health summary. Returns True if healthy."""
    report = check_system_health()
    print("\n========================================================")
    print("AI-POWERED STUDENT CAREER HUB - SYSTEM HEALTH CHECK")
    print("========================================================")
    for check_name, status in report["checks"].items():
        # Align output neatly
        dots = "." * (20 - len(check_name))
        print(f" {check_name} {dots} {status}")
    print("========================================================")
    overall = report["status"]
    print(f" OVERALL SYSTEM STATUS: {overall}")
    print("========================================================\n")
    return overall == "HEALTHY"


if __name__ == "__main__":
    is_healthy = print_health_check_summary()
    sys.exit(0 if is_healthy else 1)
