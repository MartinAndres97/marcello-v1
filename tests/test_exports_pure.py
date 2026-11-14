"""Exportaciones y estadísticas sobre datos ficticios (sin base de datos)."""
import csv
import io
import json
from datetime import datetime, timezone
from io import BytesIO

import pandas as pd
from openpyxl import load_workbook

from app.services import analytics, export_service as ex
from app.services.seed_test_data import generate_fake_payloads
from app.survey_definition import QUESTIONS, validate_answers


def make_subs(n=1000):
    subs = []
    for i, p in enumerate(generate_fake_payloads(n, seed=7)):
        clean, errors = validate_answers(p["answers"])
        assert not errors
        subs.append({"id": f"00000000-0000-4000-8000-{i:012d}", "submitted_at": p["submitted_at"], "country": p["country"],
                     "region": p["region"], "city": p["city"], "survey_version": "v1", "status": "completed",
                     "is_test": True, "answers": clean})
    return subs


def test_thousand_fake_records_are_valid_and_marked_test():
    subs = make_subs()
    assert len(subs) == 1000 and all(s["is_test"] for s in subs)


def test_xlsx_has_four_sheets_and_binary_columns():
    subs = make_subs()
    wb = load_workbook(BytesIO(ex.build_xlsx(subs)))
    assert wb.sheetnames == ["Respuestas", "Diccionario de preguntas", "Catálogo de opciones", "Estadísticas"]
    ws = wb["Respuestas"]
    assert ws.max_row == 1001  # cabecera + 1000 participantes
    header = [c.value for c in ws[1]]
    p3_cols = [i for i, h in enumerate(header) if h and h.startswith("P3_")]
    assert len(p3_cols) == 5
    for row in ws.iter_rows(min_row=2, values_only=True):
        assert all(row[i] in (0, 1) for i in p3_cols) and sum(row[i] for i in p3_cols) >= 1


def test_csv_is_utf8_one_row_per_participant():
    subs = make_subs(50)
    raw = ex.build_csv(subs)
    assert raw.startswith(b"\xef\xbb\xbf")
    df = pd.read_csv(io.BytesIO(raw), encoding="utf-8")
    assert len(df) == 50 and list(df.columns) == ex.response_columns()
    assert "Bogotá" in set(df["ciudad"]) or "Medellín" in set(df["ciudad"]) or len(df) == 50
    list(csv.reader(io.StringIO(raw.decode("utf-8-sig"))))  # parseable


def test_json_structure():
    data = json.loads(ex.build_json(make_subs(20)))
    assert data["count"] == 20
    s = data["submissions"][0]
    assert set(s) == {"id", "submitted_at", "survey_version", "status", "is_test", "location", "answers"}
    assert len(s["answers"]) == 15 and s["answers"][0]["selected"][0]["label"]


def test_formula_injection_is_neutralised():
    sub = make_subs(1)[0]
    sub["city"] = "=HYPERLINK(\"http://x\")"
    df = ex.build_responses_frame([sub])
    assert df.loc[0, "ciudad"].startswith("'=")


def test_stats_likert_mean_and_percentages():
    base = make_subs(3)
    for s, v in zip(base, (5, 4, 3)):
        s["answers"]["P2"] = [v]
        s["answers"]["P3"] = [1]
    dash = analytics.compute_dashboard(base)
    p2 = next(q for q in dash["likert"] if q["code"] == "P2")
    assert p2["mean"] == 4.0 and p2["n"] == 3
    p3 = next(q for q in dash["multiple"] if q["code"] == "P3")
    assert p3["options"][0]["count"] == 3 and p3["options"][0]["pct"] == 100.0
    assert dash["indicators"]["total"] == 3 and dash["indicators"]["completed"] == 3


def test_dashboard_geography_normalises_text():
    a, b = make_subs(2)
    a.update(country="Colombia", region="Meta", city="Villavicencio")
    b.update(country=" colombia ", region="META", city="villavicencio")
    ind = analytics.compute_dashboard([a, b])["indicators"]
    assert ind["countries"] == 1 and ind["regions"] == 1 and ind["cities"] == 1


def test_dictionary_and_catalog_cover_all_variables():
    d, c = ex.build_dictionary_frame(), ex.build_catalog_frame()
    assert set(ex.response_columns()) == set(d["variable"])
    assert len(c) == sum(len(q.options) for q in QUESTIONS)


def test_empty_export_still_valid():
    assert ex.build_xlsx([]) and ex.build_csv([]) and json.loads(ex.build_json([]))["count"] == 0
