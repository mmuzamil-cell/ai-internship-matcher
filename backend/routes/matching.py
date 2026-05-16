"""
routes/matching.py — AI-powered resume-to-internship matching endpoints.

Endpoints:
  GET /match/my-matches  → Top 20 internships ranked by cosine similarity
  GET /match/skill-gap   → Skills the student is missing from top-10 matches

How matching works:
  1. Load the student's most recently uploaded resume's skills_json.
  2. Encode skills as a sentence-transformer vector (all-MiniLM-L6-v2).
  3. Encode each internship's required_skills + description as a vector.
  4. Compute cosine similarity; save results to match_scores table.
  5. Return top-20, each annotated with matching/missing skills breakdown.
"""

import json
import logging
from collections import Counter
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import Internship, MatchScore, Resume, get_db
from models.schemas import MatchResult, SkillGapItem, SkillGapResponse
from routes.auth import get_current_user
from routes.jobs import _internship_to_schema, _parse_skills
from utils.matcher import compute_match_scores, get_matching_and_missing_skills

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/match", tags=["AI Matching"])

# ─── Hardcoded course suggestions ────────────────────────────────────────────
# Maps canonical skill names → a recommended learning URL.
# In production you could fetch these from a courses API.
COURSE_URLS: dict[str, str] = {
    "python":           "https://www.coursera.org/learn/python",
    "javascript":       "https://www.coursera.org/learn/javascript-basics",
    "typescript":       "https://www.youtube.com/watch?v=BwuLxPH8IDs",
    "java":             "https://www.coursera.org/learn/java-programming",
    "c++":              "https://www.youtube.com/watch?v=vLnPwxZdW4Y",
    "react":            "https://www.coursera.org/learn/react-basics",
    "next.js":          "https://www.youtube.com/watch?v=mTz0GXj8NN0",
    "vue":              "https://www.youtube.com/watch?v=FXpIoQ_rT_c",
    "angular":          "https://www.coursera.org/learn/angular",
    "fastapi":          "https://www.youtube.com/watch?v=0sOvCWFmrtA",
    "django":           "https://www.coursera.org/learn/django-web-framework",
    "flask":            "https://www.youtube.com/watch?v=Z1RJmh_OqeA",
    "node.js":          "https://www.coursera.org/learn/server-side-nodejs",
    "sql":              "https://www.coursera.org/learn/sql-for-data-science",
    "postgresql":       "https://www.youtube.com/watch?v=qw--VYLpxG4",
    "mongodb":          "https://www.coursera.org/learn/introduction-to-mongodb",
    "aws":              "https://www.coursera.org/learn/aws-fundamentals-going-cloud-native",
    "azure":            "https://www.coursera.org/learn/microsoft-azure-fundamentals",
    "google cloud":     "https://www.coursera.org/learn/gcp-fundamentals",
    "docker":           "https://www.youtube.com/watch?v=pg19Z8LL06w",
    "kubernetes":       "https://www.coursera.org/learn/google-kubernetes-engine",
    "git":              "https://www.coursera.org/learn/introduction-git-github",
    "machine learning": "https://www.coursera.org/learn/machine-learning",
    "deep learning":    "https://www.coursera.org/specializations/deep-learning",
    "tensorflow":       "https://www.coursera.org/learn/introduction-tensorflow",
    "pytorch":          "https://www.youtube.com/watch?v=OIenNRt2bjg",
    "data analysis":    "https://www.coursera.org/learn/data-analysis-with-python",
    "natural language processing": "https://www.coursera.org/specializations/natural-language-processing",
    "computer vision":  "https://www.coursera.org/learn/convolutional-neural-networks",
    "rest api":         "https://www.youtube.com/watch?v=WXsD0ZgxjRw",
    "agile":            "https://www.coursera.org/learn/agile-development",
    "ui/ux":            "https://www.coursera.org/professional-certificates/google-ux-design",
    "linux":            "https://www.coursera.org/learn/linux-and-bash-for-data-engineering",
    "ci/cd":            "https://www.youtube.com/watch?v=R8_veQiYBjI",
    "testing":          "https://www.coursera.org/learn/software-testing",
    "data structures":  "https://www.coursera.org/learn/algorithms-part1",
    "oop":              "https://www.coursera.org/learn/object-oriented-java",
    "pandas":           "https://www.youtube.com/watch?v=vmEHCJofslg",
    "scikit-learn":     "https://www.youtube.com/watch?v=0Lt9w-BxKFQ",
    "tableau":          "https://www.coursera.org/learn/analytics-tableau",
    "power bi":         "https://www.youtube.com/watch?v=TmhQCQr_y2A",
}

_DEFAULT_COURSE = "https://www.coursera.org/search?query={skill}"


def _get_course_url(skill: str) -> str:
    """Return a course URL for the given skill, or a Coursera search fallback."""
    return COURSE_URLS.get(skill.lower(), _DEFAULT_COURSE.format(skill=skill.replace(" ", "+")))


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.get(
    "/my-matches",
    response_model=List[MatchResult],
    summary="Get top-20 internship matches for the current user",
)
def get_my_matches(
    current_user = Depends(get_current_user),
    db: Session  = Depends(get_db),
):
    """
    AI matching pipeline:

    1. Load the student's most recently uploaded resume (latest uploaded_at).
    2. Parse skills from skills_json.
    3. Load all active internships from the database.
    4. Run sentence-transformer cosine similarity for each internship.
    5. Persist scores in match_scores (upsert: delete old, insert new).
    6. Return top 20 results with per-internship skill breakdown.
    """
    # ── Step 1: Get latest resume ──────────────────────────────────────────────
    resume = (
        db.query(Resume)
        .filter(Resume.user_id == current_user.id)
        .order_by(Resume.uploaded_at.desc())
        .first()
    )
    if not resume:
        # No resume uploaded yet — return empty list so the frontend shows an empty state
        return []

    student_skills = _parse_skills(resume.skills_json)
    if len(student_skills) < 3:
        # Not enough skills for reliable matching — return empty instead of 422
        logger.info("User %s has only %d skills, need ≥3 for matching", current_user.id, len(student_skills))
        return []

    # ── Step 2: Load all active internships ────────────────────────────────────
    jobs = db.query(Internship).filter(Internship.is_active == True).all()
    if not jobs:
        # No jobs in the database yet — return empty list
        return []

    # Convert to plain dicts for the matcher utility (avoids ORM session issues)
    jobs_data = [
        {
            "id":              j.id,
            "required_skills": j.required_skills,
            "description":     j.description or "",
        }
        for j in jobs
    ]

    # ── Step 3: Compute similarity scores ─────────────────────────────────────
    logger.info("Computing match scores for user %d against %d jobs", current_user.id, len(jobs))
    scored = compute_match_scores(student_skills, jobs_data)   # List[(id, score)]

    # ── Step 4: Persist scores to DB (delete old, insert new) ─────────────────
    db.query(MatchScore).filter(MatchScore.user_id == current_user.id).delete()
    for job_id, score in scored:
        db.add(MatchScore(user_id=current_user.id, internship_id=job_id, score=score))
    db.commit()

    # ── Step 5: Build top-20 response ─────────────────────────────────────────
    top_20_ids = [job_id for job_id, _ in scored[:20]]
    score_map  = {job_id: score for job_id, score in scored}

    # Fetch full internship objects for the top 20
    top_jobs = {j.id: j for j in db.query(Internship).filter(Internship.id.in_(top_20_ids)).all()}

    results: List[MatchResult] = []
    for job_id in top_20_ids:
        job = top_jobs.get(job_id)
        if not job:
            continue

        matching, missing = get_matching_and_missing_skills(
            student_skills       = student_skills,
            job_required_skills_json = job.required_skills or "[]",
        )

        results.append(
            MatchResult(
                internship      = _internship_to_schema(job),
                score_percent   = round(score_map[job_id] * 100, 1),
                matching_skills = matching,
                missing_skills  = missing,
            )
        )

    return results


@router.get(
    "/skill-gap",
    response_model=SkillGapResponse,
    summary="Identify skills the student is most frequently missing",
)
def get_skill_gap(
    current_user = Depends(get_current_user),
    db: Session  = Depends(get_db),
):
    """
    Skill gap analysis:

    1. Load the student's latest resume skills.
    2. Find the student's top-10 match_scores from the DB.
    3. For each of those 10 internships, compute missing skills (set difference).
    4. Count how frequently each missing skill appears across all 10 internships.
    5. Return the top missing skills with a suggested learning resource URL.

    This helps students understand what to learn next to improve their match rate.
    """
    # ── Load student's skills ──────────────────────────────────────────────────
    resume = (
        db.query(Resume)
        .filter(Resume.user_id == current_user.id)
        .order_by(Resume.uploaded_at.desc())
        .first()
    )
    if not resume:
        return SkillGapResponse(missing_skills=[])
    student_skills = _parse_skills(resume.skills_json)

    # ── Load top-10 matched internships (from pre-computed scores) ─────────────
    top_scores = (
        db.query(MatchScore)
        .filter(MatchScore.user_id == current_user.id)
        .order_by(MatchScore.score.desc())
        .limit(10)
        .all()
    )
    if not top_scores:
        return SkillGapResponse(missing_skills=[])

    # ── Aggregate missing skills across top-10 jobs ────────────────────────────
    missing_counter: Counter = Counter()
    for score_record in top_scores:
        job = score_record.internship
        _, missing = get_matching_and_missing_skills(
            student_skills           = student_skills,
            job_required_skills_json = job.required_skills or "[]",
        )
        for skill in missing:
            missing_counter[skill] += 1

    # ── Build response — show all skills missing in at least 1 top-10 job ─────
    gap_items: List[SkillGapItem] = [
        SkillGapItem(
            skill_name          = skill,
            jobs_requiring_it   = count,
            suggested_course_url= _get_course_url(skill),
        )
        for skill, count in missing_counter.most_common()   # Sorted by frequency
    ]

    return SkillGapResponse(missing_skills=gap_items)
