"""Unit tests for embedding caching, similarity math, and offline fallback."""

import numpy as np
from backend.ai.embedder import (
    embed_student,
    embed_opportunity,
    calculate_similarity,
    _fallback_pseudo_embedding,
    clear_embedding_caches
)
from backend.models.student import Student
from backend.models.opportunity import Opportunity


def test_embedding_caching():
    """Verify that repeated opportunity embedding calls utilize the in-memory cache."""
    clear_embedding_caches()
    opp = Opportunity(
        id="test-cache-1",
        title="Software Engineer Intern",
        company="Cache Corp",
        skills=["Python", "FastAPI"],
        apply_url="https://example.com"
    )

    vec1 = embed_opportunity(opp)
    vec2 = embed_opportunity(opp)

    assert isinstance(vec1, np.ndarray)
    assert vec1.shape == (384,)
    # Verify cached instance is identical
    assert vec1 is vec2


def test_calculate_similarity_bounds():
    """Verify cosine similarity produces values strictly in [0.0, 1.0]."""
    v1 = np.ones(384, dtype=np.float32)
    v2 = np.ones(384, dtype=np.float32)
    sim_identical = calculate_similarity(v1, v2)
    assert round(sim_identical, 4) == 1.0

    v3 = np.zeros(384, dtype=np.float32)
    sim_zero = calculate_similarity(v1, v3)
    assert sim_zero == 0.0


def test_fallback_pseudo_embedding():
    """Verify fallback embedding generates deterministic 384-dim normalized vector."""
    vec1 = _fallback_pseudo_embedding("Python Machine Learning")
    vec2 = _fallback_pseudo_embedding("Python Machine Learning")

    assert vec1.shape == (384,)
    assert np.allclose(vec1, vec2)
    assert np.isclose(np.linalg.norm(vec1), 1.0)
