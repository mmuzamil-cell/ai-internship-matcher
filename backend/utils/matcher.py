"""
utils/matcher.py - AI-powered resume-to-internship matching engine.

The sentence-transformer model is intentionally loaded lazily. Loading it while
FastAPI imports routes can make the whole API appear frozen before /health,
auth, jobs, or resume endpoints become available.
"""

import json
import logging
import threading
from typing import List, Tuple

import numpy as np

logger = logging.getLogger(__name__)

_MODEL_NAME = "all-MiniLM-L6-v2"
_model = None
_model_lock = threading.Lock()


def _get_model():
    """Load and return the sentence-transformer model on first match request."""
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:  # double-check locking
                try:
                    from sentence_transformers import SentenceTransformer

                    logger.info("Loading SentenceTransformer model: %s", _MODEL_NAME)
                    _model = SentenceTransformer(_MODEL_NAME)
                    logger.info("Model loaded successfully.")
                except Exception as exc:
                    logger.error("Failed to load sentence-transformer model: %s", exc)
                    raise RuntimeError(
                        f"Sentence-transformer model '{_MODEL_NAME}' is not loaded. "
                        "Install sentence-transformers and make sure the model is available."
                    ) from exc
    return _model


def _encode(text: str) -> np.ndarray:
    """
    Encode a text string into a unit-norm embedding vector.

    normalize_embeddings=True means dot-product == cosine similarity.
    """
    model = _get_model()
    return model.encode(text, normalize_embeddings=True, show_progress_bar=False)


def _cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    """Compute cosine similarity between two normalized vectors."""
    return float(np.dot(vec_a, vec_b))


def _internship_to_text(required_skills_json: str, description: str) -> str:
    """Build a single text string representing an internship for embedding."""
    skills_text = ""
    if required_skills_json:
        try:
            skills = json.loads(required_skills_json)
            skills_text = " ".join(skills)
        except (json.JSONDecodeError, TypeError):
            skills_text = ""

    desc_snippet = (description or "")[:300]
    return f"{skills_text} {desc_snippet}".strip()


def compute_match_scores(
    student_skills: List[str],
    internships: List[dict],
) -> List[Tuple[int, float]]:
    """
    Compute cosine similarity scores between a student and all internships.

    Returns a list of (internship_id, score) tuples sorted by score descending.
    """
    if not student_skills or not internships:
        return []

    student_text = " ".join(student_skills)
    student_vec = _encode(student_text)

    job_texts = []
    valid_jobs = []
    for job in internships:
        job_text = _internship_to_text(
            required_skills_json=job.get("required_skills", ""),
            description=job.get("description", ""),
        )
        if job_text:
            job_texts.append(job_text)
            valid_jobs.append(job)

    if not job_texts:
        return []

    # Batch encode all job texts
    model = _get_model()
    job_vecs = model.encode(job_texts, normalize_embeddings=True, show_progress_bar=False)

    results: List[Tuple[int, float]] = []
    for job, job_vec in zip(valid_jobs, job_vecs):
        score = _cosine_similarity(student_vec, job_vec)
        results.append((job["id"], score))

    results.sort(key=lambda item: item[1], reverse=True)
    return results



def get_matching_and_missing_skills(
    student_skills: List[str],
    job_required_skills_json: str,
) -> Tuple[List[str], List[str]]:
    """Compute exact skill overlap between a student and one job."""
    try:
        job_skills = set(json.loads(job_required_skills_json or "[]"))
    except (json.JSONDecodeError, TypeError):
        job_skills = set()

    student_set = {skill.lower() for skill in student_skills}
    job_set = {skill.lower() for skill in job_skills}

    matching = sorted(student_set & job_set)
    missing = sorted(job_set - student_set)

    return matching, missing
