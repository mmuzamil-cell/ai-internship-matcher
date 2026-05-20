"""
routes/auth.py — Authentication endpoints.

Endpoints:
  POST /auth/register  → Create a new student account
  POST /auth/login     → Exchange credentials for a JWT token
  GET  /auth/me        → Return the current user's profile (protected)
  PUT  /auth/me        → Update the current user's profile (protected)

Security approach:
  - Passwords are hashed with bcrypt (work factor 12) before storage.
  - JWTs are signed with HS256 and expire after ACCESS_TOKEN_EXPIRE_MINUTES.
  - The get_current_user dependency can be imported by any other router that
    needs a protected route.
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import bcrypt
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from database import User, get_db
from models.schemas import TokenResponse, UserCreate, UserResponse, UserUpdate
from rate_limit import LOGIN_RATE_LIMIT, limiter

load_dotenv()

# Dummy bcrypt hash used for constant-time comparison when user is not found,
# preventing timing attacks that reveal whether an email is registered.
DUMMY_HASH = "$2b$12$LJ3m4ys4Bwl.kj1vJbRYwOVBzWjFy.jXJ2T.WzOFSt4bDwxl5kDNa"

# ─── Configuration ────────────────────────────────────────────────────────────
SECRET_KEY: str  = os.getenv("SECRET_KEY", "")
ALGORITHM:  str  = os.getenv("ALGORITHM", "HS256")
EXPIRE_MIN: int  = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY is not set in environment variables.")

# Using bcrypt directly (passlib is incompatible with bcrypt>=5.0 on Python 3.14)

# OAuth2 scheme tells FastAPI where clients send their bearer token (Authorization header).
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ─── Password Helpers ─────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    """Return bcrypt hash of a plaintext password."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if plain matches the stored bcrypt hash."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


# ─── JWT Helpers ──────────────────────────────────────────────────────────────

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Build a signed JWT containing `data` as the payload.

    The 'exp' claim is set to now + expires_delta (defaults to EXPIRE_MIN).
    FastAPI's OAuth2 flow automatically reads this token from the
    Authorization: Bearer <token> header.
    """
    payload = data.copy()
    expire  = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=EXPIRE_MIN))
    payload.update({"exp": expire})
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db:    Session = Depends(get_db),
) -> User:
    """
    FastAPI dependency — decode JWT and return the authenticated User ORM object.

    Raises HTTP 401 if:
      - Token is missing or malformed
      - Token has expired
      - User referenced in token no longer exists in the DB

    Usage in other routers:
        @router.get("/protected")
        def my_route(current_user: User = Depends(get_current_user)):
            ...
    """
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id_raw: Optional[str] = payload.get("sub")
        if user_id_raw is None:
            raise credentials_error
        try:
            user_id = int(user_id_raw)
        except (ValueError, TypeError):
            raise credentials_error
    except JWTError:
        raise credentials_error

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_error
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """
    Dependency that ensures the current user has admin privileges.
    Used to protect POST /jobs and similar admin-only routes.
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required.",
        )
    return current_user


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new student account",
)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    """
    Create a new user account.

    Steps:
      1. Check email is not already registered (case-insensitive).
      2. Hash the password with bcrypt.
      3. Insert the User record and return it (without the hash).
    """
    # Email uniqueness check (case-insensitive)
    existing = db.query(User).filter(User.email == user_in.email.lower()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    new_user = User(
        full_name     = user_in.full_name.strip(),
        email         = user_in.email.lower(),          # Store lowercase for consistency
        password_hash = hash_password(user_in.password),
        university    = user_in.university,
        major         = user_in.major,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)  # Populate auto-generated fields like id, created_at
    return new_user


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login and receive a JWT access token",
)
@limiter.limit(LOGIN_RATE_LIMIT)
def login(
    request: Request,  # Required by slowapi for IP-based rate limiting
    form_data: OAuth2PasswordRequestForm = Depends(),
    db:        Session = Depends(get_db),
):
    """
    Authenticate a user and return a JWT.

    Uses OAuth2PasswordRequestForm so Swagger UI shows a built-in login form.
    The `username` field in the form should contain the user's email address.

    Rate limiting is applied via slowapi in main.py (max 5/minute per IP).
    """
    # Look up user by email (form_data.username = email per OAuth2 convention)
    user = db.query(User).filter(User.email == form_data.username.lower()).first()

    # Use constant-time comparison for both existence check and password verify
    # to prevent timing attacks that reveal whether an email is registered.
    if not user:
        verify_password(form_data.password, DUMMY_HASH)  # constant-time
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(data={"sub": str(user.id)})
    return TokenResponse(access_token=token, token_type="bearer")


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile",
)
def get_me(current_user: User = Depends(get_current_user)):
    """Return the authenticated user's profile. No DB query needed — user is already loaded."""
    return current_user


@router.put(
    "/me",
    response_model=UserResponse,
    summary="Update current user profile",
)
def update_me(
    updates:      UserUpdate,
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    """
    Update editable fields on the current user's profile.
    Only fields explicitly provided (non-None) are changed.
    Email and password changes require separate, more secure flows (not in scope here).
    """
    if updates.full_name is not None:
        current_user.full_name = updates.full_name.strip()
    if updates.university is not None:
        current_user.university = updates.university
    if updates.major is not None:
        current_user.major = updates.major

    db.commit()
    db.refresh(current_user)
    return current_user
