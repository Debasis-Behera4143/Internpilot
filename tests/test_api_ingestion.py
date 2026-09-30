"""API integration tests for opportunity ingestion, filtering, submission, and stats."""

from fastapi.testclient import TestClient
from backend.api.app import app
from backend.utils.security import create_access_token

client = TestClient(app)
client.headers["Authorization"] = f"Bearer {create_access_token({'sub': 'default_admin', 'email': 'admin@example.com', 'role': 'ADMIN'})}"



def test_get_opportunities_endpoint_and_pagination():
    """Verify listing opportunities with pagination headers."""
    response = client.get("/api/opportunities?limit=5&offset=0")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) <= 5
    assert "X-Total-Returned" in response.headers


def test_opportunity_filtering():
    """Verify filtering by remote status, type, and search query."""
    # Filter remote
    resp_remote = client.get("/api/opportunities?remote=true&limit=10")
    assert resp_remote.status_code == 200
    for item in resp_remote.json():
        assert item["remote"] is True

    # Filter search text
    resp_search = client.get("/api/opportunities?q=Engineer&limit=10")
    assert resp_search.status_code == 200


def test_opportunity_stats_endpoint():
    """Verify /api/opportunities/stats returns structured aggregation metrics."""
    response = client.get("/api/opportunities/stats")
    assert response.status_code == 200
    stats = response.json()
    assert "total" in stats
    assert "active" in stats
    assert "expired" in stats
    assert "by_source" in stats
    assert "by_type" in stats
    assert isinstance(stats["by_source"], dict)


def test_employer_submission_endpoint():
    """Verify POST /api/opportunities/submit successfully creates an opportunity with source='Employer Submission'."""
    payload = {
        "title": "Quantum Computing Intern",
        "company": "Qubit Dynamics",
        "description": "Research quantum circuit optimization and variational algorithms.",
        "apply_url": "https://qubitdynamics.example/careers/apply",
        "submission_type": "employer",
        "opportunity_type": "internship",
        "skills": ["Python", "Qiskit", "Linear Algebra"],
        "location": "Bengaluru",
        "remote": True,
        "stipend": "₹60,000 / month",
        "deadline": "2026-12-31"
    }

    response = client.post("/api/opportunities/submit", json=payload)
    assert response.status_code == 200
    created = response.json()

    assert created["title"] == "Quantum Computing Intern"
    assert created["company"] == "Qubit Dynamics"
    assert created["source"] == "Employer Submission"
    assert created["apply_url"] == "https://qubitdynamics.example/careers/apply"
    assert created["remote"] is True
    assert "Qiskit" in created["skills"]


def test_college_submission_endpoint():
    """Verify POST /api/opportunities/submit with submission_type='college' records source='College Submission'."""
    payload = {
        "title": "On-Campus Software Developer Intern",
        "company": "Infosystems Labs",
        "description": "Campus placement drive exclusive for final year undergraduates.",
        "apply_url": "https://infosystems.example/campus/apply",
        "submission_type": "college",
        "location": "Hyderabad",
        "remote": False
    }

    response = client.post("/api/opportunities/submit", json=payload)
    assert response.status_code == 200
    created = response.json()
    assert created["source"] == "College Submission"
    assert created["apply_url"] == "https://infosystems.example/campus/apply"


def test_submission_validation_errors():
    """Verify that invalid submissions are rejected with clear 422 or 400 errors."""
    # Missing company and title
    bad_payload = {
        "title": "",
        "company": "",
        "description": "Short",
        "apply_url": "not-a-valid-url"
    }
    response = client.post("/api/opportunities/submit", json=bad_payload)
    assert response.status_code in (400, 422)


def test_trigger_ingest_endpoint():
    """Verify POST /api/opportunities/ingest manually runs the pipeline and returns a report."""
    response = client.post("/api/opportunities/ingest")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "report" in data
    report = data["report"]
    assert "sources_attempted" in report
    assert "sources_successful" in report
    assert "collected" in report
    assert "duplicates_removed" in report
    assert "saved" in report
