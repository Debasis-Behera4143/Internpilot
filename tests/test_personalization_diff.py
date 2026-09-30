"""Personalization verification test confirming Student A and Student B receive distinct recommendations."""

import json
from pathlib import Path
from backend.models.opportunity import Opportunity
from backend.models.student import Student
from backend.ai.scorer import calculate_match_details
from backend.utils.config import settings


def test_personalization_differentiation():
    """Verify that Student A (AI/ML) and Student B (Web/Backend) get distinct recommendations."""
    demo_opps_file = settings.ROOT_DIR / "data" / "demo_opportunities.json"
    demo_students_file = settings.ROOT_DIR / "data" / "demo_students.json"

    assert demo_opps_file.exists()
    assert demo_students_file.exists()

    with open(demo_opps_file, "r", encoding="utf-8") as f:
        raw_opps = json.load(f)
    opportunities = [Opportunity(**o) for o in raw_opps]

    with open(demo_students_file, "r", encoding="utf-8") as f:
        raw_students = json.load(f)

    student_a = Student(**raw_students["student_a"])
    student_b = Student(**raw_students["student_b"])

    # Score all opportunities for Student A
    ranked_a = []
    for opp in opportunities:
        det = calculate_match_details(opp, student=student_a)
        ranked_a.append((opp, det["match_score"]))
    ranked_a.sort(key=lambda x: x[1], reverse=True)

    # Score all opportunities for Student B
    ranked_b = []
    for opp in opportunities:
        det = calculate_match_details(opp, student=student_b)
        ranked_b.append((opp, det["match_score"]))
    ranked_b.sort(key=lambda x: x[1], reverse=True)

    top_opp_a = ranked_a[0][0]
    top_score_a = ranked_a[0][1]

    top_opp_b = ranked_b[0][0]
    top_score_b = ranked_b[0][1]

    # Student A (AIML) top recommendation should be an AI/ML opportunity
    assert any(k in top_opp_a.title.lower() for k in ["machine learning", "ai", "nlp", "vision"])
    # Student B (Web/Backend) top recommendation should be Web/Backend
    assert any(k in top_opp_b.title.lower() for k in ["web", "frontend", "backend", "full-stack", "react", "node"])

    # Top opportunities must differ between the two students
    assert top_opp_a.id != top_opp_b.id

    # The score for Student A's top choice when evaluated by Student B should be significantly lower
    det_a_by_b = calculate_match_details(top_opp_a, student=student_b)
    assert top_score_a > det_a_by_b["match_score"]
