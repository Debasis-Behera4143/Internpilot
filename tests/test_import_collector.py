"""Unit tests for CSV and JSON import collector."""

import tempfile
from pathlib import Path
from backend.collectors.import_collector import ImportCollector


def test_import_from_csv():
    """Verify parsing and validation of a CSV opportunity file."""
    csv_content = """title,company,description,skills,location,remote,stipend,deadline,source,source_url,apply_url
AI Research Fellow,Cortex Labs,Work on multimodal transformers,"Python,PyTorch,NLP",Bengaluru,True,₹45000/mo,2026-11-30,Direct,https://cortex.example,https://cortex.example/apply
,,Missing Title and Company,,,False,,,,https://invalid.example/apply
Valid Role,Valid Org,Desc,"React,Node",Remote,True,₹25000/mo,,Campus,,https://valid.example/apply
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
        f.write(csv_content)
        temp_path = Path(f.name)

    try:
        collector = ImportCollector()
        opps = collector.parse_csv(temp_path)

        # Should have parsed 2 valid opportunities and skipped the invalid 1
        assert len(opps) == 2
        assert opps[0].title == "AI Research Fellow"
        assert opps[0].company == "Cortex Labs"
        assert "PyTorch" in opps[0].skills
        assert opps[0].apply_url == "https://cortex.example/apply"

        assert opps[1].title == "Valid Role"
        assert opps[1].company == "Valid Org"
    finally:
        temp_path.unlink(missing_ok=True)


def test_import_from_json():
    """Verify parsing and validation of a JSON opportunity file."""
    json_content = """[
        {
            "title": "Data Science Intern",
            "company": "QuantPulse",
            "description": "Financial time-series modeling",
            "skills": ["Python", "Pandas", "Scikit-learn"],
            "location": "Mumbai",
            "remote": false,
            "apply_url": "https://quantpulse.example/apply"
        },
        {
            "title": "",
            "company": "Missing Title Corp",
            "apply_url": "https://missing.example/apply"
        }
    ]"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        f.write(json_content)
        temp_path = Path(f.name)

    try:
        collector = ImportCollector()
        opps = collector.parse_json(temp_path)

        assert len(opps) == 1
        assert opps[0].title == "Data Science Intern"
        assert opps[0].company == "QuantPulse"
        assert "Python" in opps[0].skills
        assert opps[0].remote is False
    finally:
        temp_path.unlink(missing_ok=True)
