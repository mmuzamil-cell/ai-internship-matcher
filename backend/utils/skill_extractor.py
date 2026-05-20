"""
utils/skill_extractor.py — Resume skill detection using spaCy + keyword matching.

Strategy:
  1. Load spaCy's English model for tokenization and lemmatization.
  2. Normalize resume text (lowercase, remove punctuation noise).
  3. Slide a window over tokens/bigrams/trigrams and match against KNOWN_SKILLS.
  4. Return a deduplicated, sorted list of detected skills.

Why keyword matching instead of pure NER?
  spaCy's out-of-box NER doesn't recognize domain skills like "FastAPI" or
  "TensorFlow". Maintaining a curated skill list gives us precise, explainable
  detection that works reliably on resume formats.
"""

import logging
import re
from typing import List, Set

import spacy

logger = logging.getLogger(__name__)

# ─── Load spaCy Model ─────────────────────────────────────────────────────────
# en_core_web_sm is lightweight (~12 MB). Install with:
#   python -m spacy download en_core_web_sm
try:
    _nlp = spacy.load("en_core_web_sm", disable=["ner", "parser"])  # We only need tokenizer+lemma
except OSError:
    logger.warning(
        "spaCy model 'en_core_web_sm' not found. "
        "Run: python -m spacy download en_core_web_sm"
    )
    _nlp = None  # Graceful degradation — we'll fall back to simple regex matching


# ─── Canonical Skills List (60+ skills) ───────────────────────────────────────
# Keys are the canonical display name.
# Values are alternative spellings / abbreviations that should map to that skill.
# All entries are lowercase to simplify matching.

KNOWN_SKILLS: dict[str, List[str]] = {
    # Programming Languages
    "python":           ["python3", "py"],
    "javascript":       ["js", "javascript"],
    "typescript":       ["ts", "typescript"],
    "java":             ["java"],
    "c++":              ["c++", "cpp", "c plus plus"],
    "c#":               ["c#", "csharp", "c sharp"],
    "go":               ["golang"],
    "rust":             ["rust"],
    "swift":            ["swift"],
    "kotlin":           ["kotlin"],
    "php":              ["php"],
    "ruby":             ["ruby", "ruby on rails"],
    "r":                ["r programming", "rstudio"],
    "matlab":           ["matlab"],
    "scala":            ["scala"],
    "dart":             ["dart"],

    # Web Frameworks / Libraries
    "react":            ["reactjs", "react.js", "react js"],
    "next.js":          ["nextjs", "next js"],
    "vue":              ["vuejs", "vue.js", "vue js"],
    "angular":          ["angularjs", "angular.js"],
    "fastapi":          ["fastapi", "fast api"],
    "django":           ["django", "django rest framework", "drf"],
    "flask":            ["flask"],
    "express":          ["expressjs", "express.js"],
    "spring boot":      ["spring boot", "springboot"],
    "laravel":          ["laravel"],
    "node.js":          ["nodejs", "node js", "node.js"],

    # Databases
    "sql":              ["sql", "structured query language"],
    "postgresql":       ["postgresql", "postgres"],
    "mysql":            ["mysql"],
    "mongodb":          ["mongodb", "mongo"],
    "redis":            ["redis"],
    "sqlite":           ["sqlite"],
    "elasticsearch":    ["elasticsearch", "elastic search"],
    "firebase":         ["firebase", "firestore"],

    # Cloud & DevOps
    "aws":              ["amazon web services", "aws"],
    "azure":            ["microsoft azure", "azure"],
    "google cloud":     ["gcp", "google cloud platform", "google cloud"],
    "docker":           ["docker"],
    "kubernetes":       ["kubernetes", "k8s"],
    "ci/cd":            ["ci/cd", "cicd", "continuous integration", "continuous deployment"],
    "git":              ["git", "github", "gitlab", "bitbucket"],
    "linux":            ["linux", "unix", "bash", "shell scripting"],

    # AI / ML / Data Science
    "machine learning": ["machine learning", "ml"],
    "deep learning":    ["deep learning", "dl"],
    "tensorflow":       ["tensorflow", "tf"],
    "pytorch":          ["pytorch", "torch"],
    "scikit-learn":     ["sklearn", "scikit learn", "scikit-learn"],
    "pandas":           ["pandas"],
    "numpy":            ["numpy"],
    "data analysis":    ["data analysis", "data analytics", "statistical analysis"],
    "natural language processing": ["nlp", "natural language processing"],
    "computer vision":  ["computer vision", "image processing"],
    "tableau":          ["tableau"],
    "power bi":         ["power bi", "powerbi"],

    # Soft / Other Technical Skills
    "rest api":         ["rest api", "restful api", "rest apis", "api development"],
    "graphql":          ["graphql"],
    "agile":            ["agile", "scrum", "kanban"],
    "ui/ux":            ["ui/ux", "ui ux", "user interface", "user experience", "figma"],
    "testing":          ["unit testing", "pytest", "jest", "selenium", "test automation"],
    "data structures":  ["data structures", "algorithms", "dsa"],
    "oop":              ["object oriented programming", "oop", "object-oriented"],
}

# Build a flat lookup: every alias → canonical skill name
# This makes O(1) matching during scanning.
_ALIAS_TO_CANONICAL: dict[str, str] = {}
for canonical, aliases in KNOWN_SKILLS.items():
    _ALIAS_TO_CANONICAL[canonical.lower()] = canonical
    for alias in aliases:
        _ALIAS_TO_CANONICAL[alias.lower()] = canonical

# Prevent short canonical names from causing false positives
for short_name in ("go", "r", "c"):
    if short_name in _ALIAS_TO_CANONICAL and short_name == _ALIAS_TO_CANONICAL[short_name]:
        del _ALIAS_TO_CANONICAL[short_name]


def _normalize(text: str) -> str:
    """
    Lowercase and strip common punctuation that interferes with matching.
    Preserves '+', '#', '/' which appear in skill names like 'c++', 'c#', 'ci/cd'.
    """
    text = text.lower()
    # Replace noise characters with space, keep alphanumeric + skill chars
    text = re.sub(r"[^\w\s\+\#\/\.\-]", " ", text)
    # Collapse multiple whitespace
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_skills(resume_text: str) -> List[str]:
    """
    Detect skills mentioned in resume text.

    Process:
      1. Normalize text.
      2. Use spaCy tokenizer to get clean tokens (falls back to split() if spaCy unavailable).
      3. Check 1-gram, 2-gram, and 3-gram windows against the alias lookup table.
      4. Return deduplicated canonical skill names, sorted alphabetically.

    Args:
        resume_text: Raw text extracted from a PDF resume.

    Returns:
        List of canonical skill names found (e.g., ["python", "react", "sql"]).
    """
    if not resume_text:
        return []

    normalized = _normalize(resume_text)
    found_skills: Set[str] = set()

    # ── Tokenize ──────────────────────────────────────────────────────────────
    if _nlp:
        doc = _nlp(normalized)
        tokens = [token.text for token in doc if not token.is_space]
    else:
        # Fallback tokenization when spaCy model is missing
        tokens = normalized.split()

    # ── N-gram Window Matching ─────────────────────────────────────────────────
    # We check up to trigrams to catch multi-word skills like "machine learning"
    # and "natural language processing".
    n = len(tokens)
    for i in range(n):
        for gram_size in (1, 2, 3):
            if i + gram_size > n:
                break
            gram = " ".join(tokens[i : i + gram_size])
            canonical = _ALIAS_TO_CANONICAL.get(gram)
            if canonical:
                found_skills.add(canonical)

    return sorted(found_skills)


def skills_to_text(skills: List[str]) -> str:
    """
    Convert a list of skills into a single sentence for embedding.
    Used by the matcher to build the student's skill vector.

    Example: ["python", "sql", "react"] → "python sql react"
    """
    return " ".join(skills)
