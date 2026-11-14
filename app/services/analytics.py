"""Estadísticas puras (sin base de datos): reciben la lista de envíos cargada con repository.load_submissions."""
import statistics
from collections import Counter, defaultdict
from datetime import timezone

from app.survey_definition import QUESTIONS


def _utc(dt):
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _norm(s: str) -> str:
    return " ".join(s.split()).casefold()


def _group_counts(values):
    """Agrupa texto libre ignorando mayúsculas/espacios; muestra la variante más frecuente."""
    counts, variants = Counter(), defaultdict(Counter)
    for v in values:
        k = _norm(v)
        counts[k] += 1
        variants[k][" ".join(v.split())] += 1
    return [{"name": variants[k].most_common(1)[0][0], "count": c} for k, c in counts.most_common()]


def option_counts(subs):
    counts = {q.code: Counter() for q in QUESTIONS}
    n = {q.code: 0 for q in QUESTIONS}
    for s in subs:
        for code, vals in s["answers"].items():
            if code in counts:
                n[code] += 1
                counts[code].update(vals)
    return counts, n


def likert_summary(counter: Counter) -> dict:
    values = [v for v, c in sorted(counter.items()) for _ in range(c)]
    n = len(values)
    if n == 0:
        return {"n": 0, "mean": None, "median": None, "std": None, "min": None, "max": None}
    return {
        "n": n,
        "mean": round(statistics.fmean(values), 2),
        "median": statistics.median(values),
        "std": round(statistics.stdev(values), 2) if n > 1 else 0.0,
        "min": min(values),
        "max": max(values),
    }


def compute_dashboard(subs) -> dict:
    counts, n = option_counts(subs)
    total = len(subs)

    def options_block(q):
        c, nn = counts[q.code], n[q.code]
        return [
            {"value": i, "label": label, "count": c[i], "pct": round(100 * c[i] / nn, 1) if nn else 0.0}
            for i, label in enumerate(q.options, start=1)
        ]

    by_date = Counter(_utc(s["submitted_at"]).date().isoformat() for s in subs)
    regions_key = {(_norm(s["country"]), _norm(s["region"])) for s in subs}
    cities_key = {(_norm(s["country"]), _norm(s["region"]), _norm(s["city"])) for s in subs}
    countries_key = {_norm(s["country"]) for s in subs}

    return {
        "indicators": {
            "total": total,
            "completed": sum(1 for s in subs if s["status"] == "completed"),
            "profiles": sum(1 for v in counts["P1"].values() if v > 0),
            "regions": len(regions_key),
            "cities": len(cities_key),
            "countries": len(countries_key),
        },
        "by_profile": [{"value": o["value"], "label": o["label"], "count": o["count"]}
                       for o in options_block(next(q for q in QUESTIONS if q.code == "P1"))],
        "by_date": [{"date": d, "count": c} for d, c in sorted(by_date.items())],
        "geography": {
            "countries": _group_counts([s["country"] for s in subs])[:15],
            "regions": _group_counts([f'{s["region"]} ({s["country"]})' for s in subs])[:15],
            "cities": _group_counts([f'{s["city"]} ({s["country"]})' for s in subs])[:15],
        },
        "likert": [
            {"code": q.code, "text": q.text, **likert_summary(counts[q.code]), "distribution": options_block(q)}
            for q in QUESTIONS if q.qtype == "likert"
        ],
        "multiple": [
            {"code": q.code, "text": q.text, "n": n[q.code], "options": options_block(q)}
            for q in QUESTIONS if q.qtype == "multiple"
        ],
        "single": [
            {"code": q.code, "text": q.text, "n": n[q.code], "options": options_block(q)}
            for q in QUESTIONS if q.qtype == "single"
        ],
    }
