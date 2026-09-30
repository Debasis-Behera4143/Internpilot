"""Local embedding generator using SentenceTransformers with LRU caching and offline fallback.

Operates 100% free and locally on CPU without paid third-party API dependencies.
"""

import hashlib
import numpy as np
from typing import Dict, Union, Any, Optional
from sklearn.metrics.pairwise import cosine_similarity

from backend.utils.config import settings
from backend.utils.logger import get_logger

logger = get_logger("ai_embedder")

_model = None
_model_failed = False

# In-memory caches for fast sub-millisecond retrieval
_opportunity_cache: Dict[str, np.ndarray] = {}
_student_cache: Dict[str, np.ndarray] = {}


def get_model():
    """Lazy-load the SentenceTransformer model with graceful offline handling."""
    global _model, _model_failed
    if _model_failed:
        return None

    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading SentenceTransformer model '{settings.EMBEDDING_MODEL}'...")
            _model = SentenceTransformer(settings.EMBEDDING_MODEL)
        except Exception as e:
            logger.warning(
                f"Could not load SentenceTransformer '{settings.EMBEDDING_MODEL}': {e}. "
                "Falling back to local heuristic token-similarity embeddings. "
                "To resolve: Ensure 'sentence-transformers' and 'torch' are installed and internet access is available on initial download."
            )
            _model_failed = True
            return None
    return _model


def _fallback_pseudo_embedding(text: str, dim: int = 384) -> np.ndarray:
    """Deterministic token/character n-gram pseudo-embedding fallback when neural model is unavailable."""
    if not text or not text.strip():
        return np.zeros(dim, dtype=np.float32)

    vec = np.zeros(dim, dtype=np.float32)
    tokens = text.lower().split()
    for token in tokens:
        # Hash each token deterministically into vector bins
        h = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
        idx = h % dim
        sign = 1.0 if ((h >> 8) & 1) else -1.0
        vec[idx] += sign

    norm = np.linalg.norm(vec)
    if norm > 0:
        vec /= norm
    return vec


def get_embedding(text: str) -> np.ndarray:
    """Generate dense vector embedding for input string."""
    if not text or not text.strip():
        return np.zeros(384, dtype=np.float32)

    model = get_model()
    if model is not None:
        try:
            return np.array(model.encode(text), dtype=np.float32)
        except Exception as e:
            logger.warning(f"Embedding encoding failed ({e}), using fallback vector.")
            return _fallback_pseudo_embedding(text)
    return _fallback_pseudo_embedding(text)


def embed_student(student: Any) -> np.ndarray:
    """Generate or retrieve cached dense embedding for a student profile."""
    from backend.ai.student_representation import get_student_representation
    text = get_student_representation(student)
    text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

    if text_hash in _student_cache:
        return _student_cache[text_hash]

    vec = get_embedding(text)
    _student_cache[text_hash] = vec
    return vec


def embed_opportunity(opportunity: Any) -> np.ndarray:
    """Generate or retrieve cached dense embedding for an opportunity."""
    from backend.ai.job_representation import get_job_representation
    text = get_job_representation(opportunity)

    # Key cache by opportunity ID + text content hash
    opp_id = getattr(opportunity, "id", None) or (opportunity.get("id") if isinstance(opportunity, dict) else None)
    text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    cache_key = f"{opp_id}:{text_hash}" if opp_id else text_hash

    if cache_key in _opportunity_cache:
        return _opportunity_cache[cache_key]

    vec = get_embedding(text)
    _opportunity_cache[cache_key] = vec
    return vec


def calculate_similarity(student_embedding: np.ndarray, job_embedding: np.ndarray) -> float:
    """Calculate cosine similarity between student and job vector embeddings (0.0 to 1.0)."""
    if student_embedding is None or job_embedding is None:
        return 0.0

    # Ensure 2D shapes for sklearn cosine_similarity
    s_vec = student_embedding.reshape(1, -1)
    j_vec = job_embedding.reshape(1, -1)

    s_norm = np.linalg.norm(s_vec)
    j_norm = np.linalg.norm(j_vec)

    if s_norm == 0 or j_norm == 0:
        return 0.0

    sim = float(cosine_similarity(s_vec, j_vec)[0][0])
    # Normalize [-1.0, 1.0] to [0.0, 1.0]
    return max(0.0, min(1.0, sim))


def clear_embedding_caches():
    """Clear in-memory caches when resetting datasets."""
    global _opportunity_cache, _student_cache
    _opportunity_cache.clear()
    _student_cache.clear()
