from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_db_url


@lru_cache
def get_engine():
    return create_engine(get_db_url(), pool_pre_ping=True)


@lru_cache
def get_sessionmaker():
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_db():
    db = get_sessionmaker()()
    try:
        yield db
    finally:
        db.close()
