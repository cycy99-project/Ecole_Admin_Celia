import os
import secrets
from typing import Optional

from fastapi import Request, HTTPException, status
import bcrypt
from itsdangerous import URLSafeSerializer, BadSignature
from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import Admin

DEFAULT_ADMIN_USERNAME = "prof"
DEFAULT_ADMIN_PASSWORD = "PROF2026"
COOKIE_NAME = "rdv_session"
COOKIE_MAX_AGE = 60 * 60 * 24 * 7  # 7 jours

_secret_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", ".secret")
_secret_path = os.path.abspath(_secret_path)


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


def make_session_token(admin_id: int) -> str:
    return serializer.dumps({"admin_id": admin_id})


def read_session_token(token: str) -> Optional[int]:
    try:
        data = serializer.loads(token)
        return int(data["admin_id"])
    except (BadSignature, KeyError, ValueError, TypeError):
        return None


def get_current_admin(request: Request) -> Optional[Admin]:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    admin_id = read_session_token(token)
    if admin_id is None:
        return None
    db: Session = SessionLocal()
    try:
        return db.get(Admin, admin_id)
    finally:
        db.close()


def require_admin(request: Request) -> Admin:
    admin = get_current_admin(request)
    if admin is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentification requise",
        )
    return admin


def seed_default_admin(db: Session) -> None:
    existing = db.query(Admin).filter(Admin.username == DEFAULT_ADMIN_USERNAME).first()
    if existing:
        return
    if db.query(Admin).count() > 0:
        return
    admin = Admin(
        username=DEFAULT_ADMIN_USERNAME,
        password_hash=hash_password(DEFAULT_ADMIN_PASSWORD),
        must_change_password=True,
    )
    db.add(admin)
    db.commit()
