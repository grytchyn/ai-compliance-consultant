"""
Auth module for AI Verify.
Handles Google OAuth token verification, JWT creation/validation, and user management.
"""
import uuid
import os
import logging
from datetime import datetime, timedelta
from typing import Optional

import jwt
import requests
from fastapi import Depends, HTTPException, Header
from sqlalchemy.orm import Session

from .database import SessionLocal, User

logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────
GOOGLE_CLIENT_ID = "945886082965-7sr7hpo44cs44snba4a6cbk1nv5ii0n7.apps.googleusercontent.com"
JWT_SECRET = os.getenv("JWT_SECRET", "ai-verify-jwt-secret-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24 * 7  # 7 days


def verify_google_token(id_token: str) -> Optional[dict]:
    """
    Verify a Google ID token using Google's tokeninfo endpoint.
    Returns the token payload (user info) if valid, None otherwise.
    """
    try:
        resp = requests.get(
            "https://oauth2.googleapis.com/tokeninfo",
            params={"id_token": id_token},
            timeout=10,
        )
        if resp.status_code != 200:
            logger.warning(f"Google token verification failed: {resp.status_code}")
            return None

        payload = resp.json()

        # Verify it's our client
        if payload.get("aud") != GOOGLE_CLIENT_ID:
            logger.warning(f"Token audience mismatch: {payload.get('aud')}")
            return None

        return {
            "sub": payload["sub"],
            "email": payload.get("email", ""),
            "name": payload.get("name", ""),
            "picture": payload.get("picture", ""),
        }
    except Exception as e:
        logger.error(f"Google token verification error: {e}")
        return None


def create_jwt(user: User) -> str:
    """Create a JWT for an authenticated user."""
    now = datetime.utcnow()
    payload = {
        "sub": user.id,
        "email": user.email,
        "name": user.name,
        "iat": now,
        "exp": now + timedelta(hours=JWT_EXPIRY_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_jwt(token: str) -> Optional[dict]:
    """Decode and validate a JWT. Returns payload or None."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("JWT expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid JWT: {e}")
        return None


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_current_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """
    Extract and validate the current user from the Authorization header.
    Returns None if no valid auth.
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None

    token = authorization.replace("Bearer ", "")
    payload = decode_jwt(token)
    if not payload:
        return None

    user = db.query(User).filter(User.id == payload.get("sub")).first()
    return user


def login_or_register(google_data: dict, db: Session) -> tuple[User, str]:
    """
    Given verified Google data, find or create the user.
    Returns (user, jwt_token).
    """
    user = db.query(User).filter(User.google_sub == google_data["sub"]).first()

    if not user:
        # Also check by email
        user = db.query(User).filter(User.email == google_data.get("email", "")).first()

    if user:
        # Update existing user info
        if google_data.get("name"):
            user.name = google_data["name"]
        if google_data.get("picture"):
            user.avatar_url = google_data["picture"]
        user.last_login = datetime.utcnow()
        db.commit()
        db.refresh(user)
    else:
        # Create new user
        user = User(
            id=str(uuid.uuid4()),
            google_sub=google_data["sub"],
            email=google_data.get("email", ""),
            name=google_data.get("name", ""),
            avatar_url=google_data.get("picture", ""),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info(f"New user registered: {user.email} ({user.id})")

    token = create_jwt(user)
    return user, token
