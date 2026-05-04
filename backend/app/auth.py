import os
import secrets
from typing import Optional

from fastapi import Request, HTTPException, status
import bcrypt
from itsdangerous import URLSafeSerializer, BadSignature
from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import User, ROLE_SUPER_ADMIN

DEFAULT_SUPER_ADMIN_USERNAME = "prof"
DEFAULT_SUPER_ADMIN_PASSWORD = "PROF2026"
DEFAULT_TEACHER_PASSWORD = "Bienvenue123"
COOKIE_NAME = "rdv_session"
COOKIE_MAX_AGE = 60 * 60 * 24 * 7  # 7 jours

# Cookie sécurisé en production (HTTPS via Caddy). Activé via env COOKIE_SECURE=1.
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "0") == "1"

from .database import DATA_DIR
_secret_path = str(DATA_DIR / ".secret")


def _get_or_create_secret() -> str:
    if os.path.exists(_secret_path):
        with open(_secret_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    secret = secrets.token_urlsafe(48)
    os.makedirs(os.path.dirname(_secret_path), exist_ok=True)
    with open(_secret_path, "w", encoding="utf-8") as f:
        f.write(secret)
    return secret


SECRET_KEY = _get_or_create_secret()
serializer = URLSafeSerializer(SECRET_KEY, salt="rdv-ecole-session")


def _to_bytes(password: str) -> bytes:
    # bcrypt limite à 72 octets, on tronque silencieusement si besoin
    return password.encode("utf-8")[:72]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_to_bytes(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(_to_bytes(password), password_hash.encode("utf-8"))
    except ValueError:
        return False


def make_session_token(user_id: int) -> str:
    return serializer.dumps({"user_id": user_id})


def read_session_token(token: str) -> Optional[int]:
    try:
        data = serializer.loads(token)
        return int(data["user_id"])
    except (BadSignature, KeyError, ValueError, TypeError):
        return None


def get_current_user(request: Request) -> Optional[User]:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    user_id = read_session_token(token)
    if user_id is None:
        return None
    db: Session = SessionLocal()
    try:
        user = db.get(User, user_id)
        if user and not user.is_active:
            return None
        return user
    finally:
        db.close()


def require_user(request: Request) -> User:
    user = get_current_user(request)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentification requise",
        )
    return user


def require_super_admin(request: Request) -> User:
    user = require_user(request)
    if not user.is_super_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès super-admin requis")
    return user


def seed_default_super_admin(db: Session) -> None:
    existing = db.query(User).filter(User.username == DEFAULT_SUPER_ADMIN_USERNAME).first()
    if existing:
        return
    if db.query(User).count() > 0:
        return
    user = User(
        username=DEFAULT_SUPER_ADMIN_USERNAME,
        full_name="Direction",
        password_hash=hash_password(DEFAULT_SUPER_ADMIN_PASSWORD),
        must_change_password=True,
        role=ROLE_SUPER_ADMIN,
        class_level=None,
        is_active=True,
    )
    db.add(user)
    db.commit()
