"""Construcción de exportaciones (Excel, CSV, JSON) y respaldos pg_dump.

Las funciones build_* son puras: reciben la lista de envíos (repository.load_submissions)
y no tocan la base de datos, por lo que se pueden probar sin PostgreSQL.
"""
import json
import logging
import os
import shutil
import subprocess
from datetime import timezone
from io import BytesIO

import pandas as pd
from openpyxl.styles import Font, PatternFill

from app.services import analytics
from app.survey_definition import QUESTIONS, SURVEY_CODE

log = logging.getLogger("marcello.export")

BASE_COLUMNS = [
    ("id_envio", "UUID del envío"),
    ("fecha_utc", "Fecha y hora de envío (UTC, ISO 8601)"),
    ("version_encuesta", "Versión de la encuesta"),
    ("pais", "País (autodeclarado)"),
    ("departamento", "Departamento o región (autodeclarado)"),
    ("ciudad", "Ciudad (autodeclarada)"),
    ("estado", "Estado del envío"),
    ("es_prueba", "1 = registro ficticio de prueba, 0 = real"),
]
TYPE_LABEL = {"single": "selección única", "multiple": "selección múltiple", "likert": "escala Likert 1-5"}


def iso_utc(dt) -> str:
    dt = dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _safe(text):
    """Evita inyección de fórmulas al abrir CSV/Excel (=, +, -, @ al inicio)."""
    return "'" + text if isinstance(text, str) and text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def question_variables(q):
    """[(nombre_columna, valor_opción | None, descripción)] de una pregunta."""
    if q.qtype == "multiple":
        return [(f"{q.code}_{i}", i, f"{q.code} · {label} (1 = seleccionada, 0 = no)")
                for i, label in enumerate(q.options, start=1)]
    if q.qtype == "single":
        return [(q.code, None, f"{q.code} · valor de la opción elegida (1-{len(q.options)})"),
                (f"{q.code}_etiqueta", None, f"{q.code} · texto de la opción elegida")]
    return [(q.code, None, f"{q.code} · valor Likert (1-5)")]


def response_columns():
    cols = [c for c, _ in BASE_COLUMNS]
    for q in QUESTIONS:
        cols += [c for c, _, _ in question_variables(q)]
    return cols


def build_responses_frame(subs) -> pd.DataFrame:
    rows = []
    for s in subs:
        row = {
            "id_envio": s["id"], "fecha_utc": iso_utc(s["submitted_at"]),
            "version_encuesta": s["survey_version"], "pais": _safe(s["country"]),
            "departamento": _safe(s["region"]), "ciudad": _safe(s["city"]),
            "estado": s["status"], "es_prueba": int(bool(s["is_test"])),
        }
        for q in QUESTIONS:
            vals = s["answers"].get(q.code, [])
            if q.qtype == "multiple":
                for i in range(1, len(q.options) + 1):
                    row[f"{q.code}_{i}"] = 1 if i in vals else 0
            elif q.qtype == "single":
                v = vals[0] if vals else None
                row[q.code] = v
                row[f"{q.code}_etiqueta"] = q.options[v - 1] if v else None
            else:
                row[q.code] = vals[0] if vals else None
        rows.append(row)
    return pd.DataFrame(rows, columns=response_columns())


def build_dictionary_frame() -> pd.DataFrame:
    rows = [{"variable": c, "pregunta": "", "texto_pregunta": "", "tipo": "metadato", "descripcion": d}
            for c, d in BASE_COLUMNS]
    for q in QUESTIONS:
        for col, _, desc in question_variables(q):
            rows.append({"variable": col, "pregunta": q.code, "texto_pregunta": q.text,
                         "tipo": TYPE_LABEL[q.qtype], "descripcion": desc})
    return pd.DataFrame(rows)


def build_catalog_frame() -> pd.DataFrame:
    rows = []
    for q in QUESTIONS:
        variables = question_variables(q)
        for i, label in enumerate(q.options, start=1):
            var = variables[i - 1][0] if q.qtype == "multiple" else variables[0][0]
            rows.append({"pregunta": q.code, "tipo": TYPE_LABEL[q.qtype], "valor": i, "etiqueta": label, "variable": var})
    return pd.DataFrame(rows)


def build_stats_frame(subs) -> pd.DataFrame:
    counts, n = analytics.option_counts(subs)
    rows = []
    for q in QUESTIONS:
        for i, label in enumerate(q.options, start=1):
            c = counts[q.code][i]
            rows.append({"pregunta": q.code, "texto": q.text, "tipo": TYPE_LABEL[q.qtype], "valor": i,
                         "opcion": label, "frecuencia": c,
                         "porcentaje": round(100 * c / n[q.code], 1) if n[q.code] else 0.0,
                         "n": n[q.code], "media": None, "mediana": None, "desv_est": None})
        if q.qtype == "likert":
            sm = analytics.likert_summary(counts[q.code])
            rows.append({"pregunta": q.code, "texto": q.text, "tipo": TYPE_LABEL[q.qtype], "valor": None,
                         "opcion": "RESUMEN", "frecuencia": None, "porcentaje": None, "n": sm["n"],
                         "media": sm["mean"], "mediana": sm["median"], "desv_est": sm["std"]})
    return pd.DataFrame(rows)


def _style_sheet(ws):
    fill = PatternFill("solid", fgColor="0E7490")
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = fill
    ws.freeze_panes = "A2"
    for col in ws.columns:
        width = max(len(str(c.value)) if c.value is not None else 0 for c in list(col)[:200])
        ws.column_dimensions[col[0].column_letter].width = min(max(width + 2, 8), 60)


def build_xlsx(subs) -> bytes:
    sheets = [
        ("Respuestas", build_responses_frame(subs)),
        ("Diccionario de preguntas", build_dictionary_frame()),
        ("Catálogo de opciones", build_catalog_frame()),
        ("Estadísticas", build_stats_frame(subs)),
    ]
    bio = BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        for name, df in sheets:
            df.to_excel(writer, sheet_name=name, index=False)
            _style_sheet(writer.sheets[name])
    return bio.getvalue()


def build_csv(subs) -> bytes:
    # UTF-8 con BOM: Excel lo abre con acentos correctos; pandas, R y Power BI lo leen sin problema.
    text = build_responses_frame(subs).to_csv(index=False, lineterminator="\r\n")
    return ("\ufeff" + text).encode("utf-8")


def build_json(subs) -> bytes:
    by_code = {q.code: q for q in QUESTIONS}
    items = []
    for s in subs:
        answers = []
        for code in (q.code for q in QUESTIONS):
            q = by_code[code]
            answers.append({
                "question": code, "text": q.text, "type": q.qtype,
                "selected": [{"value": v, "label": q.options[v - 1]} for v in s["answers"].get(code, [])],
            })
        items.append({
            "id": s["id"], "submitted_at": iso_utc(s["submitted_at"]), "survey_version": s["survey_version"],
            "status": s["status"], "is_test": bool(s["is_test"]),
            "location": {"country": s["country"], "region": s["region"], "city": s["city"]},
            "answers": answers,
        })
    payload = {"survey": SURVEY_CODE, "count": len(items), "submissions": items}
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


class BackupError(RuntimeError):
    pass


def run_pg_dump(fmt: str) -> bytes:
    """Respaldo restaurable con pg_dump. fmt: 'sql' (texto plano) o 'dump' (formato custom)."""
    from app.config import get_db_url

    if fmt not in ("sql", "dump"):
        raise ValueError("formato inválido")
    exe = shutil.which("pg_dump")
    if not exe:
        raise BackupError("pg_dump no está instalado en este entorno")
    url = get_db_url()
    cmd = [exe, "--no-owner", "--no-privileges", "--clean", "--if-exists", "--no-password",
           "--format=" + ("plain" if fmt == "sql" else "custom"),
           "-h", url.host or "localhost", "-p", str(url.port or 5432), "-U", url.username, "-d", url.database]
    env = dict(os.environ, PGPASSWORD=url.password or "")
    result = subprocess.run(cmd, capture_output=True, env=env, timeout=300, check=False)
    if result.returncode != 0:
        log.error("pg_dump falló: %s", result.stderr.decode("utf-8", "replace"))
        raise BackupError("pg_dump terminó con error")
    return result.stdout
