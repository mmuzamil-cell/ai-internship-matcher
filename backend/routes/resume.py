"""
routes/resume.py — Resume upload and management endpoints.

Endpoints:
  POST   /resume/upload      → Upload a PDF, extract text & skills, save to DB
  GET    /resume/my-resumes  → List all resumes for the current user
  DELETE /resume/{id}        → Delete a resume (owner only)
"""

import json
import logging
import os
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from database import Resume, get_db
from models.schemas import ResumeResponse
from routes.auth import get_current_user
from utils.pdf_parser import extract_text_from_pdf
from utils.skill_extractor import extract_skills

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/resume", tags=["Resume"])

# ─── Constants ────────────────────────────────────────────────────────────────
MAX_FILE_SIZE   = 5 * 1024 * 1024   # 5 MB in bytes
MIN_SKILLS_FOR_MATCH = 3            # Minimum skills needed for reliable matching
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "uploads/resumes"))


def _build_resume_response(resume: Resume) -> ResumeResponse:
    """
    Convert a Resume ORM object to a ResumeResponse schema.
    Parses the skills_json string back into a Python list.
    """
    try:
        skills: list = json.loads(resume.skills_json or "[]")
    except (json.JSONDecodeError, TypeError):
        skills = []

    return ResumeResponse(
        id           = resume.id,
        filename     = resume.filename,
        skills_found = skills,
        total_skills = len(skills),
        match_ready  = len(skills) >= MIN_SKILLS_FOR_MATCH,
        uploaded_at  = resume.uploaded_at,
    )


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.post(
    "/upload",
    response_model=ResumeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a PDF resume and extract skills",
)
async def upload_resume(
    file:         UploadFile  = File(..., description="PDF resume (max 5 MB)"),
    current_user              = Depends(get_current_user),
    db:           Session     = Depends(get_db),
):
    """
    Process a student's PDF resume:
      1. Validate file type (must be PDF) and size (max 5 MB).
      2. Read bytes into memory and extract text with PyPDF2.
      3. Detect skills from text using spaCy keyword matching.
      4. Save the file to disk at uploads/resumes/user_{id}_{filename}.
      5. Save a Resume record to the database.
      6. Return the skill list and match_ready flag.
    """
    # ── Validate file type ────────────────────────────────────────────────────
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are accepted. Please upload a .pdf resume.",
        )

    # ── Read file bytes & check size ──────────────────────────────────────────
    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds the 5 MB size limit. Please compress your PDF.",
        )

    # ── Extract text from PDF ──────────────────────────────────────────────────
    extracted_text = extract_text_from_pdf(file_bytes)
    if not extracted_text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Could not extract text from this PDF. "
                "It may be a scanned image or password-protected file. "
                "Please use a text-based PDF."
            ),
        )

    # ── Detect skills ──────────────────────────────────────────────────────────
    skills = extract_skills(extracted_text)
    skills_json = json.dumps(skills)

    # ── Save file to disk ──────────────────────────────────────────────────────
    # Create directory if it doesn't exist (safe for concurrent requests)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    # Sanitize filename: replace spaces, prepend user ID for namespacing
    safe_name  = file.filename.replace(" ", "_")
    save_name  = f"user_{current_user.id}_{safe_name}"
    save_path  = UPLOAD_DIR / save_name

    # Write asynchronously to avoid blocking the event loop
    async with aiofiles.open(save_path, "wb") as out_file:
        await out_file.write(file_bytes)

    logger.info("Saved resume for user %d: %s (%d bytes)", current_user.id, save_name, len(file_bytes))

    # ── Save record to database ───────────────────────────────────────────────
    resume = Resume(
        user_id        = current_user.id,
        filename       = file.filename,         # Show original name to user
        file_path      = str(save_path),        # Absolute path for server-side use
        extracted_text = extracted_text,
        skills_json    = skills_json,
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)

    return _build_resume_response(resume)


@router.get(
    "/my-resumes",
    response_model=list[ResumeResponse],
    summary="List all resumes uploaded by the current user",
)
def list_my_resumes(
    current_user = Depends(get_current_user),
    db: Session  = Depends(get_db),
):
    """
    Return all Resume records belonging to the current user, newest first.
    Includes parsed skill lists for each resume.
    """
    resumes = (
        db.query(Resume)
        .filter(Resume.user_id == current_user.id)
        .order_by(Resume.uploaded_at.desc())
        .all()
    )
    return [_build_resume_response(r) for r in resumes]


@router.delete(
    "/{resume_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a resume (owner only)",
)
def delete_resume(
    resume_id:   int,
    current_user = Depends(get_current_user),
    db: Session  = Depends(get_db),
):
    """
    Delete a resume from both the filesystem and the database.
    Only the owner of the resume can delete it (no admin override here).
    Returns 204 No Content on success.
    """
    resume = db.query(Resume).filter(Resume.id == resume_id).first()

    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Resume with id={resume_id} not found.",
        )

    # Ownership check — prevent one user from deleting another's resume
    if resume.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this resume.",
        )

    # Delete the file from disk (fail gracefully if file is already missing)
    file_path = Path(resume.file_path)
    if file_path.exists():
        file_path.unlink()
        logger.info("Deleted resume file: %s", file_path)
    else:
        logger.warning("Resume file not found on disk (already deleted?): %s", file_path)

    # Delete the DB record
    db.delete(resume)
    db.commit()
    # 204 — return nothing


# ─── CV Builder Integration ───────────────────────────────────────────────────

from pydantic import BaseModel, Field
from typing import List as TList, Optional as TOptional

class CVEducation(BaseModel):
    school: str = ""
    degree: str = ""
    field: str = ""
    start: str = ""
    end: str = ""
    gpa: str = ""

class CVExperience(BaseModel):
    company: str = ""
    role: str = ""
    start: str = ""
    end: str = ""
    description: str = ""

class CVProject(BaseModel):
    name: str = ""
    tech: str = ""
    description: str = ""
    link: str = ""

class CVData(BaseModel):
    """Full CV data from the CV Builder form."""
    name: str = Field("", max_length=200)
    email: str = Field("", max_length=255)
    phone: str = Field("", max_length=50)
    location: str = Field("", max_length=200)
    linkedin: str = Field("", max_length=300)
    github: str = Field("", max_length=300)
    portfolio: str = Field("", max_length=300)
    summary: str = Field("", max_length=2000)
    education: TList[CVEducation] = []
    experience: TList[CVExperience] = []
    skills: str = Field("", max_length=2000)
    projects: TList[CVProject] = []
    certifications: str = Field("", max_length=2000)
    languages: str = Field("", max_length=500)


@router.post(
    "/from-cv",
    response_model=ResumeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Save CV Builder data as a resume and extract skills for matching",
)
def save_cv_as_resume(
    cv: CVData,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Accept structured CV data from the CV Builder, convert it into plain text,
    extract skills using the same skill extractor as PDF resumes, and save as
    a Resume record. This makes the CV data available for AI matching.
    """
    # ── Build plain text from all CV sections ─────────────────────────────────
    parts = []

    if cv.name:
        parts.append(cv.name)
    if cv.summary:
        parts.append(f"Summary: {cv.summary}")

    for ed in cv.education:
        if ed.school or ed.degree:
            parts.append(
                f"Education: {ed.degree} in {ed.field} at {ed.school} "
                f"({ed.start}-{ed.end}) GPA: {ed.gpa}"
            )

    for ex in cv.experience:
        if ex.company or ex.role:
            parts.append(
                f"Experience: {ex.role} at {ex.company} ({ex.start}-{ex.end}). "
                f"{ex.description}"
            )

    if cv.skills:
        parts.append(f"Skills: {cv.skills}")

    for proj in cv.projects:
        if proj.name:
            parts.append(
                f"Project: {proj.name}. Technologies: {proj.tech}. "
                f"{proj.description}"
            )

    if cv.certifications:
        parts.append(f"Certifications: {cv.certifications}")
    if cv.languages:
        parts.append(f"Languages: {cv.languages}")

    full_text = "\n\n".join(parts)

    if not full_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CV is empty. Please fill in at least some sections.",
        )

    # ── Extract skills ────────────────────────────────────────────────────────
    # Also include the comma-separated skills directly so they're always detected
    skill_text = full_text + " " + cv.skills.replace(",", " ")
    detected_skills = extract_skills(skill_text)

    # Also add any comma-separated skills the user typed that the extractor missed
    user_skills = [s.strip().lower() for s in cv.skills.split(",") if s.strip()]
    all_skills = list(dict.fromkeys(detected_skills + [s for s in user_skills if s]))
    skills_json = json.dumps(all_skills)

    # ── Save as Resume record ─────────────────────────────────────────────────
    resume = Resume(
        user_id=current_user.id,
        filename=f"cv_builder_{cv.name.replace(' ', '_') or 'resume'}.pdf",
        file_path="cv_builder",  # No physical file
        extracted_text=full_text,
        skills_json=skills_json,
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)

    logger.info(
        "Saved CV Builder resume for user %d: %d skills detected",
        current_user.id, len(all_skills),
    )

    return _build_resume_response(resume)

