"""Fixtures. Las pruebas con base de datos usan SOLO una base cuyo nombre termina en "_test"."""
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
ADMIN_USER = "admin_test"
ADMIN_PASSWORD = "test-admin-password-123"


def _skip_or_fail(msg):
    if os.environ.get("REQUIRE_DB") == "1":
        pytest.fail(msg, pytrace=False)
    pytest.skip(msg)


@pytest.fixture(scope="session")
def db_env():
    try:
        import psycopg2
        from psycopg2 import sql
        from sqlalchemy.engine import URL, make_url
    except ImportError as exc:
        _skip_or_fail(f"Dependencias de base de datos no instaladas: {exc}")

    explicit = os.environ.get("TEST_DATABASE_URL")
    url = make_url(explicit) if explicit else URL.create(
        "postgresql+psycopg2", username=os.environ.get("POSTGRES_USER", "marcello"),
        password=os.environ.get("POSTGRES_PASSWORD", ""), host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")), database=os.environ.get("TEST_DB_NAME", "marcello_test"))
    if not (url.database or "").endswith("_test"):
        pytest.fail("Por seguridad, las pruebas solo corren contra una base cuyo nombre termina en '_test'", pytrace=False)
    try:
        admin = psycopg2.connect(host=url.host, port=url.port or 5432, user=url.username, password=url.password, dbname="postgres")
    except Exception as exc:  # noqa: BLE001
        _skip_or_fail(f"No hay conexión con PostgreSQL ({exc}). Use: docker compose --profile test run --rm tests")
    admin.autocommit = True
    with admin.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (url.database,))
        if not cur.fetchone():
            cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(url.database)))
    admin.close()

    os.environ.update({
        "DATABASE_URL": url.render_as_string(hide_password=False),
        "SECRET_KEY": "test-secret-key-0123456789abcdef0123456789abcdef",
        "ADMIN_USER": ADMIN_USER, "ADMIN_PASSWORD": ADMIN_PASSWORD, "COOKIE_SECURE": "false",
    })
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    command.upgrade(cfg, "head")  # prueba también la migración
    return url


@pytest.fixture()
def db_session(db_env):
    from sqlalchemy import text

    from app.database import get_sessionmaker

    with get_sessionmaker()() as db:
        db.execute(text("TRUNCATE answer_options, answers, submissions RESTART IDENTITY CASCADE"))
        db.commit()
        yield db


@pytest.fixture()
def client(db_session):
    from fastapi.testclient import TestClient

    from app import security
    from app.main import app

    security.reset_limiters()
    with TestClient(app) as c:  # arranca el lifespan (siembra la encuesta v1)
        yield c


@pytest.fixture()
def admin_client(client):
    res = client.post("/api/admin/login", json={"username": ADMIN_USER, "password": ADMIN_PASSWORD})
    assert res.status_code == 200
    return client


@pytest.fixture()
def fake_1000(client, db_session):
    from app.services.seed_test_data import insert_fake_submissions

    assert insert_fake_submissions(db_session, 1000) == 1000
    return 1000


def valid_payload(**over):
    payload = {
        "country": "Colombia", "region": "Bogotá D.C.", "city": "Bogotá",
        "answers": {"P1": [4], "P2": [4], "P3": [1, 2], "P4": [5], "P5": [1], "P6": [3], "P7": [1, 5], "P8": [4],
                    "P9": [2], "P10": [5], "P11": [3], "P12": [4], "P13": [1, 2, 3], "P14": [1], "P15": [6]},
    }
    payload.update(over)
    return payload
