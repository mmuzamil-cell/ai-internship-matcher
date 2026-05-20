"""
rate_limit.py — Shared rate limiter instance.

Extracted into its own module to avoid circular imports between
main.py (which registers exception handlers) and routes/auth.py
(which applies the @limiter.limit decorator on login).
"""

import os

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

# Configurable via environment variable; defaults to 5/minute for production safety
LOGIN_RATE_LIMIT: str = os.getenv("LOGIN_RATE_LIMIT", "5/minute")
