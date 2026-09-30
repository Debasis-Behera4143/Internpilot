"""Outreach generator for professional recruiter and hiring manager messages."""

from typing import Union, Dict, Any, Optional
from backend.utils.logger import get_logger

logger = get_logger("ai_outreach")

_generator = None
_generator_failed = False


from backend.utils.config import settings

def _get_generator():
    """Lazily load the text-generation pipeline if enabled, with graceful fallback."""
    global _generator, _generator_failed
    if not settings.ENABLE_NEURAL_OUTREACH:
        return None

    if _generator is None and not _generator_failed:
        try:
            from transformers import pipeline
            logger.info("Initializing local distilgpt2 text-generation pipeline...")
            _generator = pipeline("text-generation", model="distilgpt2")
        except Exception as e:
            logger.warning(f"Could not load HuggingFace distilgpt2 pipeline: {e}. Using deterministic template generation.")
            _generator_failed = True
    return _generator


def generate_outreach(job: Union[Dict[str, Any], Any], candidate_summary: Optional[str] = None) -> str:
    """Generate concise professional LinkedIn outreach message.
    Accepts both legacy job dict and Opportunity models.
    """
    if hasattr(job, "title"):
        title = job.title
        company = getattr(job, "company", "your team")
        source = getattr(job, "source", "Opportunity Hub")
    else:
        title = job.get("title", "Opportunity")
        company = job.get("company", "your team")
        source = job.get("source", "the platform")

    if not candidate_summary:
        candidate_summary = "Pre-final year engineering student passionate about Machine Learning and Software Engineering"

    generator = _get_generator()
    if generator is not None:
        try:
            prompt = f"Hi! I noticed the {title} opening at {company}. As a {candidate_summary}, I would love to connect."
            result = generator(prompt, max_length=90, num_return_sequences=1)
            generated_text = result[0]["generated_text"].strip()
            if len(generated_text) > 20:
                return generated_text
        except Exception as e:
            logger.debug(f"Generator inference error: {e}")

    # High quality, professional recruiter outreach template fallback
    return (
        f"Hi [Hiring Manager / Recruiter],\n\n"
        f"I recently noticed the {title} opportunity at {company} via {source}. "
        f"As a {candidate_summary}, I have built projects and honed practical skills directly relevant to your team's goals. "
        f"I would welcome the opportunity to connect and discuss how my background can add immediate value to {company}.\n\n"
        f"Best regards,\n[My Name]"
    )
