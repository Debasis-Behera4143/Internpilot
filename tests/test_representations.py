"""Unit tests for student and opportunity text representation synthesizers."""

from backend.ai.student_representation import get_student_representation
from backend.ai.job_representation import get_job_representation
from backend.models.student import Student
from backend.models.opportunity import Opportunity


def test_student_representation():
    """Verify synthesized student representation contains all critical criteria."""
    student = Student(
        name="Candidate A",
        education="B.Tech",
        branch="Computer Science & Engineering",
        skills=["Python", "PyTorch", "SQL"],
        preferred_roles=["ML Intern"],
        preferred_locations=["Bengaluru", "Remote"],
        remote_preference=True,
        projects=["Deep Learning Transformer System"],
        experience=["AI Lab Assistant"],
        bio="Passionate engineer."
    )
    rep = get_student_representation(student)
    assert "Computer Science & Engineering" in rep
    assert "Python" in rep
    assert "PyTorch" in rep
    assert "ML Intern" in rep
    assert "Remote" in rep
    assert "Deep Learning Transformer System" in rep


def test_job_representation():
    """Verify synthesized job representation contains title, company, skills, location, remote, eligibility."""
    opp = Opportunity(
        title="AI Research Intern",
        company="Acme AI",
        opportunity_type="internship",
        skills=["Python", "Deep Learning"],
        location="Bengaluru",
        remote=True,
        experience="Fresher / Student",
        eligibility="B.Tech AIML",
        description="Build state-of-the-art vision models.",
        apply_url="https://example.com/apply"
    )
    rep = get_job_representation(opp)
    assert "AI Research Intern at Acme AI" in rep
    assert "Python, Deep Learning" in rep
    assert "Bengaluru" in rep
    assert "Remote: Yes" in rep
    assert "Fresher / Student" in rep
    assert "B.Tech AIML" in rep


def test_empty_representations():
    """Verify graceful handling when objects have minimal or missing fields."""
    empty_student = Student(name="Minimal Student")
    s_rep = get_student_representation(empty_student)
    assert len(s_rep) > 10

    empty_job = Opportunity(title="Minimal Job", apply_url="https://example.com")
    j_rep = get_job_representation(empty_job)
    assert len(j_rep) > 10
