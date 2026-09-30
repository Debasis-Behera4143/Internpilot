"""Unit tests for skill dictionary, aliases, and regex extraction."""

from backend.ai.skill_dictionary import (
    canonicalize_skill,
    extract_skills_from_text,
    SKILL_TAXONOMY,
    SKILL_ALIASES
)


def test_canonicalize_skill_aliases():
    """Verify alias mapping to standard canonical forms."""
    assert canonicalize_skill("ml") == "Machine Learning"
    assert canonicalize_skill("Machine Learning") == "Machine Learning"
    assert canonicalize_skill("tf") == "TensorFlow"
    assert canonicalize_skill("tensorflow") == "TensorFlow"
    assert canonicalize_skill("pytorch") == "PyTorch"
    assert canonicalize_skill("torch") == "PyTorch"
    assert canonicalize_skill("react.js") == "React"
    assert canonicalize_skill("reactjs") == "React"
    assert canonicalize_skill("node") == "Node.js"
    assert canonicalize_skill("postgres") == "PostgreSQL"
    assert canonicalize_skill("k8s") == "Kubernetes"
    assert canonicalize_skill("aws") == "AWS"
    assert canonicalize_skill("js") == "JavaScript"
    assert canonicalize_skill("cpp") == "C++"
    assert canonicalize_skill("c++") == "C++"


def test_extract_skills_from_text():
    """Verify accurate skill extraction from raw text without substring collisions."""
    text = (
        "I am an AIML undergraduate experienced with Python, PyTorch, and TensorFlow. "
        "Built web backends using FastAPI and PostgreSQL, containerized with Docker on Linux. "
        "Also learned React and Node.js for frontend."
    )
    skills = extract_skills_from_text(text)

    assert "Python" in skills
    assert "PyTorch" in skills
    assert "TensorFlow" in skills
    assert "FastAPI" in skills
    assert "PostgreSQL" in skills
    assert "Docker" in skills
    assert "Linux" in skills
    assert "React" in skills
    assert "Node.js" in skills


def test_extract_skills_word_boundary_safety():
    """Verify single-letter and short acronyms don't false-trigger on English words."""
    text = "We are going to make a clear case for going fast and reading books."
    skills = extract_skills_from_text(text)
    # Ensure 'go' in 'going' doesn't extract 'Go', 'c' in 'clear' doesn't extract 'C', etc.
    assert "Go" not in skills
    assert "C" not in skills
    assert "R" not in skills


def test_extract_skills_empty_text():
    """Verify safe handling of empty or whitespace text."""
    assert extract_skills_from_text("") == []
    assert extract_skills_from_text("   ") == []
    assert canonicalize_skill("") == ""
