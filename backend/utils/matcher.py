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
_use_fallback = False


def _get_model():
    """Load and return the sentence-transformer model on first match request, or None if unavailable."""
    global _model, _use_fallback
    if _use_fallback:
        return None
    if _model is None:
        with _model_lock:
            if _model is None:  # double-check locking
                try:
                    from sentence_transformers import SentenceTransformer

                    logger.info("Loading SentenceTransformer model: %s", _MODEL_NAME)
                    _model = SentenceTransformer(_MODEL_NAME)
                    logger.info("Model loaded successfully.")
                except Exception as exc:
                    logger.warning(
                        "Could not load SentenceTransformer (probably running in low-memory environment like Render). "
                        "Falling back to high-performance keyword matching. Details: %s", exc
                    )
                    _use_fallback = True
                    return None
    return _model


def _encode(text: str) -> np.ndarray:
    """
    Encode a text string into a unit-norm embedding vector.

    normalize_embeddings=True means dot-product == cosine similarity.
    """
    model = _get_model()
    if model is None:
        raise RuntimeError("Sentence-transformer model is not loaded.")
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
    Compute similarity scores between a student and all internships.
    Uses Semantic embeddings if available, otherwise falls back to a robust keyword overlap score.
    """
    if not student_skills or not internships:
        return []

    model = _get_model()
    if model is not None:
        try:
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

            if job_texts:
                job_vecs = model.encode(job_texts, normalize_embeddings=True, show_progress_bar=False)
                results: List[Tuple[int, float]] = []
                for job, job_vec in zip(valid_jobs, job_vecs):
                    score = _cosine_similarity(student_vec, job_vec)
                    results.append((job["id"], float(score)))

                # Add remaining jobs with 0 score
                scored_ids = {r[0] for r in results}
                for job in internships:
                    if job["id"] not in scored_ids:
                        results.append((job["id"], 0.0))

                results.sort(key=lambda item: item[1], reverse=True)
                return results
        except Exception as exc:
            logger.error("Error during semantic match execution, falling back: %s", exc)

    # Keyword Matching Fallback (Uses 0MB RAM, extremely fast, works on Render Free Tier)
    logger.info("Running lightweight keyword matching fallback.")
    student_set = {s.lower().strip() for s in student_skills if s}
    results = []
    for job in internships:
        job_skills_list = []
        req_skills = job.get("required_skills")
        if req_skills:
            try:
                if isinstance(req_skills, list):
                    job_skills_list = req_skills
                elif isinstance(req_skills, str):
                    job_skills_list = json.loads(req_skills)
            except Exception:
                job_skills_list = []

        job_set = {j.lower().strip() for j in job_skills_list if j}

        # 1. Direct skills overlap
        if job_set:
            overlap = student_set & job_set
            skills_score = len(overlap) / len(job_set)
        else:
            skills_score = 0.0

        # 2. Description keyword search
        desc_lower = (job.get("description") or "").lower()
        desc_matches = sum(1 for s in student_set if s in desc_lower)
        desc_score = desc_matches / max(len(student_set), 5)

        # Combined score (70% direct skill, 30% description context)
        score = 0.7 * skills_score + 0.3 * min(desc_score, 1.0)
        results.append((job["id"], float(score)))

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
