"""Configuración desde variables de entorno (nunca desde código)."""
import os
from dataclasses import dataclass
from functools import lru_cache

import bcrypt


def get_db_url():
    """URL de PostgreSQL. DATABASE_URL tiene prioridad; si no, se arma con POSTGRES_*."""
    from sqlalchemy.engine import URL, make_url

    explicit = os.environ.get("DATABASE_URL")
    if explicit:
        return make_url(explicit)
    password = os.environ.get("POSTGRES_PASSWORD", "")
    if not password:
        raise RuntimeError("Defina POSTGRES_PASSWORD (o DATABASE_URL) en el entorno / archivo .env")
    return URL.create(
        "postgresql+psycopg2",
        username=os.environ.get("POSTGRES_USER", "marcello"),
        password=password,
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        database=os.environ.get("POSTGRES_DB", "marcello"),
    )


@dataclass(frozen=True)
class Settings:
    db_url: object
    secret_key: str
    admin_user: str
    admin_password_hash: bytes
    cookie_secure: bool
    session_hours: int


def hash_password(password: str) -> bytes:
    # bcrypt solo usa los primeros 72 bytes
    return bcrypt.hashpw(password.encode("utf-8")[:72], bcrypt.gensalt(rounds=12))


@lru_cache
def get_settings() -> Settings:
    secret = os.environ.get("SECRET_KEY", "")
    if len(secret) < 32 or secret.lower().startswith("change"):
        raise RuntimeError("SECRET_KEY debe tener al menos 32 caracteres (genere una con: openssl rand -hex 32)")
    user = os.environ.get("ADMIN_USER", "").strip()
    if not user:
        raise RuntimeError("Defina ADMIN_USER en el archivo .env")
    pw_hash = os.environ.get("ADMIN_PASSWORD_HASH", "").strip()
    if pw_hash:
        hashed = pw_hash.encode("utf-8")
    else:
        pw = os.environ.get("ADMIN_PASSWORD", "")
        if len(pw) < 10 or pw.lower().startswith("change"):
            raise RuntimeError("ADMIN_PASSWORD debe tener al menos 10 caracteres (o defina ADMIN_PASSWORD_HASH)")
        hashed = hash_password(pw)
    return Settings(
        db_url=get_db_url(),
        secret_key=secret,
        admin_user=user,
        admin_password_hash=hashed,
        cookie_secure=os.environ.get("COOKIE_SECURE", "false").lower() in ("1", "true", "yes"),
        session_hours=int(os.environ.get("SESSION_HOURS", "8")),
    )
