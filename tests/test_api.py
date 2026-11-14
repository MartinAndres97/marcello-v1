"""Pruebas de integración contra PostgreSQL real (base *_test)."""
import io
import json
import shutil
import uuid
from io import BytesIO

import pandas as pd
import pytest
from openpyxl import load_workbook
from sqlalchemy import func, select, text

from tests.conftest import ADMIN_PASSWORD, ADMIN_USER, valid_payload

ADMIN_URLS = ["/api/admin/me", "/api/admin/dashboard", "/api/admin/submissions",
              "/api/admin/export/xlsx", "/api/admin/export/csv", "/api/admin/export/json",
              "/api/admin/export/postgres.sql", "/api/admin/export/postgres.dump"]


def test_health_and_postgres_connection(client, db_session):
    from app.models import Question

    assert client.get("/health").json() == {"status": "ok", "database": "ok"}
    assert "PostgreSQL" in db_session.scalar(text("select version()"))
    assert db_session.scalar(select(func.count()).select_from(Question)) == 15


def test_public_pages_and_survey_definition(client):
    assert "MARCELLO" in client.get("/").text
    survey = client.get("/api/survey").json()
    assert len(survey["questions"]) == 15


def test_valid_submission_is_stored_normalised(client, db_session):
    from app.models import Answer, AnswerOption, Submission

    res = client.post("/api/survey/submissions", json=valid_payload())
    assert res.status_code == 201
    sub = db_session.get(Submission, uuid.UUID(res.json()["id"]))
    assert sub.status == "completed" and sub.is_test is False and sub.city == "Bogotá"
    assert sub.submitted_at.utcoffset().total_seconds() == 0
    assert db_session.scalar(select(func.count()).select_from(Answer)) == 15
    expected = sum(len(v) for v in valid_payload()["answers"].values())
    assert db_session.scalar(select(func.count()).select_from(AnswerOption)) == expected


@pytest.mark.parametrize("mutate", [
    lambda p: p["answers"].pop("P15"),
    lambda p: p["answers"].update(P2=[6]),
    lambda p: p["answers"].update(P2=[0]),
    lambda p: p["answers"].update(P3=[]),
    lambda p: p["answers"].update(P3=[1, 1]),
    lambda p: p["answers"].update(P1=[1, 2]),
    lambda p: p["answers"].update(P4=[2.5]),
    lambda p: p["answers"].update(P4=[True]),
    lambda p: p["answers"].update(P99=[1]),
    lambda p: p.update(city=""),
    lambda p: p.update(city="<script>alert(1)</script>"),
    lambda p: p.update(email="a@b.com"),
    lambda p: p.update(latitude=4.6, longitude=-74.0),
])
def test_invalid_submissions_rejected_and_not_stored(client, db_session, mutate):
    from app.models import Submission

    payload = valid_payload()
    mutate(payload)
    assert client.post("/api/survey/submissions", json=payload).status_code == 422
    assert db_session.scalar(select(func.count()).select_from(Submission)) == 0


def test_submission_without_location_is_accepted(client, db_session):
    from app.models import Submission

    payload = valid_payload()
    for k in ("country", "region", "city"):
        payload.pop(k)
    assert client.post("/api/survey/submissions", json=payload).status_code == 201
    sub = db_session.scalar(select(Submission))
    assert (sub.country, sub.region, sub.city) == ("No informado",) * 3


def test_submission_rate_limit(client):
    codes = [client.post("/api/survey/submissions", json=valid_payload()).status_code for _ in range(32)]
    assert codes.count(201) == 30 and codes[-1] == 429


@pytest.mark.parametrize("url", ADMIN_URLS)
def test_admin_api_requires_login(client, url):
    assert client.get(url).status_code == 401


def test_admin_page_redirects_and_login_flow(client):
    r = client.get("/admin", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/admin/login"
    assert client.post("/api/admin/login", json={"username": ADMIN_USER, "password": "mala"}).status_code == 401
    assert client.post("/api/admin/login", json={"username": ADMIN_USER, "password": ADMIN_PASSWORD}).status_code == 200
    assert client.get("/admin").status_code == 200
    assert client.get("/api/admin/me").status_code == 200
    client.post("/api/admin/logout")
    assert client.get("/api/admin/me").status_code == 401


def test_login_is_rate_limited(client):
    codes = [client.post("/api/admin/login", json={"username": "x", "password": "y"}).status_code for _ in range(7)]
    assert codes[:5] == [401] * 5 and codes[5:] == [429, 429]


def test_dashboard_statistics_from_real_submissions(admin_client):
    for v in (5, 4, 3):
        p = valid_payload()
        p["answers"]["P2"] = [v]
        assert admin_client.post("/api/survey/submissions", json=p).status_code == 201
    d = admin_client.get("/api/admin/dashboard").json()
    assert d["indicators"]["total"] == 3 and d["indicators"]["profiles"] == 1 and d["indicators"]["cities"] == 1
    assert next(q for q in d["likert"] if q["code"] == "P2")["mean"] == 4.0


def test_test_data_never_mixes_with_real_results(admin_client, fake_1000):
    assert admin_client.post("/api/survey/submissions", json=valid_payload()).status_code == 201
    assert admin_client.get("/api/admin/dashboard").json()["indicators"]["total"] == 1
    assert admin_client.get("/api/admin/dashboard?include_test=true").json()["indicators"]["total"] == 1001
    assert admin_client.get("/api/admin/submissions").json()["total"] == 1
    assert admin_client.get("/api/admin/submissions?include_test=true").json()["total"] == 1001
    assert json.loads(admin_client.get("/api/admin/export/json").content)["count"] == 1


def test_admin_table_search_filter_pagination_detail(admin_client, fake_1000):
    q = "include_test=true"
    page = admin_client.get(f"/api/admin/submissions?{q}&page=2&page_size=50").json()
    assert page["total"] == 1000 and len(page["items"]) == 50 and page["page"] == 2
    vig = admin_client.get(f"/api/admin/submissions?{q}&city=vigo&page_size=200").json()
    assert 0 < vig["total"] < 1000 and all(i["city"] == "Vigo" for i in vig["items"])
    prof = admin_client.get(f"/api/admin/submissions?{q}&profile=3&page_size=200").json()
    assert prof["total"] > 0 and all(i["profile_value"] == 3 for i in prof["items"])
    assert admin_client.get(f"/api/admin/submissions?{q}&q=%25").json()["total"] == 0  # % se trata como texto literal
    assert admin_client.get(f"/api/admin/submissions?{q}&date_from=2000-01-01&date_to=2000-01-02").json()["total"] == 0
    first = page["items"][0]["id"]
    d = admin_client.get(f"/api/admin/submissions/{first}").json()
    assert d["id"] == first and len(d["answers"]) == 15
    assert admin_client.get("/api/admin/submissions/00000000-0000-4000-8000-000000000000").status_code == 404


def test_sql_injection_attempt_is_inert(admin_client, fake_1000):
    r = admin_client.get("/api/admin/submissions", params={"q": "'; DROP TABLE submissions; --", "include_test": "true"})
    assert r.status_code == 200 and r.json()["total"] == 0
    assert admin_client.get("/api/admin/submissions?include_test=true").json()["total"] == 1000


def test_exports_with_1000_records(admin_client, fake_1000):
    r = admin_client.get("/api/admin/export/xlsx?include_test=true")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    wb = load_workbook(BytesIO(r.content))
    assert wb.sheetnames == ["Respuestas", "Diccionario de preguntas", "Catálogo de opciones", "Estadísticas"]
    assert wb["Respuestas"].max_row == 1001

    r = admin_client.get("/api/admin/export/csv?include_test=true")
    df = pd.read_csv(io.BytesIO(r.content))
    assert len(df) == 1000 and df["es_prueba"].eq(1).all() and set(df["P3_1"]) <= {0, 1}

    r = admin_client.get("/api/admin/export/json?include_test=true")
    data = json.loads(r.content)
    assert data["count"] == 1000 and data["submissions"][0]["answers"][0]["question"] == "P1"


@pytest.mark.skipif(shutil.which("pg_dump") is None, reason="pg_dump no instalado en este entorno (sí lo está en la imagen Docker)")
def test_postgres_backups(admin_client, fake_1000):
    sql = admin_client.get("/api/admin/export/postgres.sql")
    assert sql.status_code == 200 and b"PostgreSQL database dump" in sql.content and b"submissions" in sql.content
    dump = admin_client.get("/api/admin/export/postgres.dump")
    assert dump.status_code == 200 and dump.content.startswith(b"PGDMP")
