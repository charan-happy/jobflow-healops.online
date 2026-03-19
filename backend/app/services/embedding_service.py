"""
Semantic embedding service using sentence-transformers.
Runs locally, completely free. Uses all-MiniLM-L6-v2 (384-dim, ~90MB).
"""

import logging

logger = logging.getLogger(__name__)

_model = None


def _get_model():
    """Lazy-load the sentence-transformer model."""
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _model = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("Loaded sentence-transformers model: all-MiniLM-L6-v2")
        except ImportError:
            logger.warning("sentence-transformers not installed, embeddings disabled")
            return None
        except Exception as e:
            logger.warning(f"Failed to load embedding model: {e}")
            return None
    return _model


def generate_job_embedding(title: str, description: str, skills: list[str]) -> list[float] | None:
    """Generate 384-dim embedding for a job posting."""
    model = _get_model()
    if model is None:
        return None

    skills_str = ", ".join(skills[:20]) if skills else ""
    text = f"Job: {title}. Skills: {skills_str}. {description[:500]}"

    try:
        return model.encode(text).tolist()
    except Exception as e:
        logger.warning(f"Failed to generate job embedding: {e}")
        return None


def generate_profile_embedding(
    roles: list[str],
    skills: list[str],
    experience_years: int | None,
    certifications: list[str] | None = None,
) -> list[float] | None:
    """Generate 384-dim embedding for a user profile."""
    model = _get_model()
    if model is None:
        return None

    parts = []
    if roles:
        parts.append(f"Target roles: {', '.join(roles)}")
    if skills:
        parts.append(f"Skills: {', '.join(skills[:20])}")
    if experience_years:
        parts.append(f"{experience_years} years experience")
    if certifications:
        parts.append(f"Certifications: {', '.join(certifications[:10])}")

    text = ". ".join(parts)

    try:
        return model.encode(text).tolist()
    except Exception as e:
        logger.warning(f"Failed to generate profile embedding: {e}")
        return None
