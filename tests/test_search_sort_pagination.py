"""Tests for opportunity search, filtering, sorting, pagination, and detail API."""

from fastapi.testclient import TestClient
from backend.api.app import app
from backend.services.opportunity_service import get_all_opportunities
from backend.utils.security import create_access_token

client = TestClient(app)
client.headers["Authorization"] = f"Bearer {create_access_token({'sub': 'default_admin', 'email': 'admin@example.com', 'role': 'ADMIN'})}"



def test_opportunity_search_and_filter():
    """Verify search by keyword and filtering by remote, type, and source."""
    # Search by keyword
    res = client.get("/api/opportunities?q=Engineer")
    assert res.status_code == 200
    items = res.json()
    assert isinstance(items, list)

    # Filter remote
    res_remote = client.get("/api/opportunities?remote=true")
    assert res_remote.status_code == 200
    for o in res_remote.json():
        assert o["remote"] is True

    # Filter by source
    res_source = client.get("/api/opportunities?source=internshala")
    assert res_source.status_code == 200
    for o in res_source.json():
        assert "internshala" in o["source"].lower()


def test_opportunity_sorting():
    """Verify sorting opportunities by deadline, title, company, and newest."""
    # Sort by title
    res_title = client.get("/api/opportunities?sort_by=title&limit=20")
    assert res_title.status_code == 200
    titles = [o["title"].lower() for o in res_title.json()]
    assert titles == sorted(titles)

    # Sort by deadline
    res_deadline = client.get("/api/opportunities?sort_by=deadline&limit=20")
    assert res_deadline.status_code == 200
    items = res_deadline.json()
    assert len(items) > 0


def test_opportunity_pagination_headers():
    """Verify pagination limits, offsets, and response headers."""
    res = client.get("/api/opportunities?limit=5&offset=0")
    assert res.status_code == 200
    items = res.json()
    assert len(items) <= 5
    assert res.headers.get("X-Limit") == "5"
    assert res.headers.get("X-Offset") == "0"
    assert "X-Total-Returned" in res.headers


def test_opportunity_detail_and_404():
    """Verify single opportunity lookup and 404 response for invalid IDs."""
    opps = get_all_opportunities()
    assert len(opps) > 0
    target_opp = opps[0]

    # Valid ID
    res = client.get(f"/api/opportunities/{target_opp.id}")
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == target_opp.id
    assert data["apply_url"] == target_opp.apply_url

    # Invalid ID
    res_404 = client.get("/api/opportunities/non_existent_id_4040404")
    assert res_404.status_code == 404
