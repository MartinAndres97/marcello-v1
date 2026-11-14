"""Datos FICTICIOS para pruebas. Siempre se guardan con is_test = true.

  python -m app.services.seed_test_data --n 1000     # crea 1000 envíos ficticios
  python -m app.services.seed_test_data --purge      # borra TODOS los envíos is_test
El panel y las exportaciones excluyen is_test por defecto.
"""
import argparse
import random
from datetime import datetime, timedelta, timezone

from app.survey_definition import QUESTIONS

GEO = [
    ("Colombia", "Bogotá D.C.", "Bogotá"), ("Colombia", "Antioquia", "Medellín"), ("Colombia", "Valle del Cauca", "Cali"),
    ("Colombia", "Arauca", "Arauca"), ("Colombia", "Meta", "Villavicencio"), ("España", "Galicia", "Vigo"),
    ("España", "Madrid", "Madrid"), ("Alemania", "Baviera", "Múnich"), ("México", "Jalisco", "Guadalajara"),
    ("Chile", "Región Metropolitana", "Santiago"),
]


def generate_fake_payloads(n: int, seed: int = 1234, now=None) -> list:
    rng = random.Random(seed)
    now = now or datetime.now(timezone.utc)
    out = []
    for _ in range(n):
        country, region, city = rng.choice(GEO)
        answers = {}
        for q in QUESTIONS:
            k = len(q.options)
            if q.qtype == "likert":
                answers[q.code] = [rng.choices(range(1, 6), weights=[1, 2, 4, 6, 5])[0]]
            elif q.qtype == "single":
                answers[q.code] = [rng.randint(1, k)]
            else:
                answers[q.code] = sorted(rng.sample(range(1, k + 1), rng.randint(1, k)))
        out.append({"country": country, "region": region, "city": city, "answers": answers,
                    "submitted_at": now - timedelta(minutes=rng.randint(0, 30 * 24 * 60))})
    return out


def insert_fake_submissions(db, n: int = 1000, seed: int = 1234) -> int:
    from app.services import repository

    survey = repository.get_survey(db)
    lookup = repository.load_lookup(db, survey.id)
    subs = [repository.build_submission(survey.id, lookup, p, is_test=True, submitted_at=p["submitted_at"])
            for p in generate_fake_payloads(n, seed)]
    db.add_all(subs)
    db.commit()
    return len(subs)


def purge_test_data(db) -> int:
    from sqlalchemy import delete

    from app.models import Submission

    res = db.execute(delete(Submission).where(Submission.is_test.is_(True)))
    db.commit()
    return res.rowcount


if __name__ == "__main__":
    from app.database import get_sessionmaker
    from app.seed import seed_survey

    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--purge", action="store_true")
    args = ap.parse_args()
    with get_sessionmaker()() as session:
        seed_survey(session)
        if args.purge:
            print(f"Eliminados {purge_test_data(session)} envíos de prueba")
        else:
            print(f"Insertados {insert_fake_submissions(session, args.n, args.seed)} envíos ficticios (is_test = true)")
