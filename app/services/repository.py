"""Acceso a datos con SQLAlchemy (consultas parametrizadas; nunca SQL concatenado)."""
import uuid
from collections import defaultdict
from datetime import datetime, time, timedelta, timezone

from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import Session

from app.models import Answer, AnswerOption, Question, QuestionOption, Submission, SurveyVersion
from app.survey_definition import SURVEY_CODE


def get_survey(db: Session, code: str = SURVEY_CODE) -> SurveyVersion:
    sv = db.scalar(select(SurveyVersion).where(SurveyVersion.code == code))
    if sv is None:
        raise RuntimeError(f"La versión de encuesta '{code}' no existe en la base de datos")
    return sv


def load_lookup(db: Session, survey_id: int) -> dict:
    """{(código_pregunta, valor_opción): (question_id, option_id)}"""
    rows = db.execute(
        select(Question.code, QuestionOption.value, Question.id, QuestionOption.id)
        .select_from(Question).join(QuestionOption, QuestionOption.question_id == Question.id)
        .where(Question.survey_version_id == survey_id)
    )
    return {(code, value): (qid, oid) for code, value, qid, oid in rows}


def build_submission(survey_id: int, lookup: dict, payload: dict, *, is_test=False, submitted_at=None) -> Submission:
    sub = Submission(
        id=uuid.uuid4(), survey_version_id=survey_id, country=payload["country"], region=payload["region"],
        city=payload["city"], submitted_at=submitted_at or datetime.now(timezone.utc),
        status="completed", is_test=is_test,
    )
    for code, values in payload["answers"].items():
        qid = lookup[(code, values[0])][0]
        sub.answers.append(Answer(question_id=qid, selected=[AnswerOption(option_id=lookup[(code, v)][1]) for v in values]))
    return sub


def store_submission(db: Session, payload: dict) -> Submission:
    survey = get_survey(db)
    sub = build_submission(survey.id, load_lookup(db, survey.id), payload)
    db.add(sub)
    db.commit()
    return sub


def load_submissions(db: Session, include_test: bool = False) -> list:
    """Carga todos los envíos como dicts (para estadísticas y exportaciones)."""
    q = select(Submission, SurveyVersion.code).join(SurveyVersion, SurveyVersion.id == Submission.survey_version_id)
    if not include_test:
        q = q.where(Submission.is_test.is_(False))
    subs = db.execute(q.order_by(Submission.submitted_at, Submission.id)).all()

    aq = (select(Answer.submission_id, Question.code, QuestionOption.value)
          .select_from(AnswerOption)
          .join(Answer, AnswerOption.answer_id == Answer.id)
          .join(Question, Answer.question_id == Question.id)
          .join(QuestionOption, AnswerOption.option_id == QuestionOption.id)
          .join(Submission, Answer.submission_id == Submission.id))
    if not include_test:
        aq = aq.where(Submission.is_test.is_(False))
    answers = defaultdict(lambda: defaultdict(list))
    for sid, code, value in db.execute(aq):
        answers[sid][code].append(value)

    return [
        {"id": str(s.id), "submitted_at": s.submitted_at, "country": s.country, "region": s.region,
         "city": s.city, "survey_version": version, "status": s.status, "is_test": s.is_test,
         "answers": {c: sorted(v) for c, v in answers.get(s.id, {}).items()}}
        for s, version in subs
    ]


def _profile_subquery():
    return (select(Answer.submission_id.label("sid"), QuestionOption.value.label("pv"), QuestionOption.label.label("pl"))
            .select_from(Answer)
            .join(Question, Question.id == Answer.question_id)
            .join(AnswerOption, AnswerOption.answer_id == Answer.id)
            .join(QuestionOption, QuestionOption.id == AnswerOption.option_id)
            .where(Question.code == "P1").subquery())


def _like(term: str) -> str:
    return "%" + term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def list_submissions(db: Session, *, page=1, page_size=25, q=None, profile=None, country=None, region=None,
                     city=None, date_from=None, date_to=None, include_test=False):
    prof = _profile_subquery()
    conds = []
    if not include_test:
        conds.append(Submission.is_test.is_(False))
    if q:
        like = _like(q.strip())
        conds.append(or_(Submission.city.ilike(like, escape="\\"), Submission.region.ilike(like, escape="\\"),
                         Submission.country.ilike(like, escape="\\"),
                         cast(Submission.id, String).ilike(like, escape="\\"), prof.c.pl.ilike(like, escape="\\")))
    if profile:
        conds.append(prof.c.pv == profile)
    for col, term in ((Submission.country, country), (Submission.region, region), (Submission.city, city)):
        if term:
            conds.append(col.ilike(_like(term.strip()), escape="\\"))
    if date_from:
        conds.append(Submission.submitted_at >= datetime.combine(date_from, time.min, tzinfo=timezone.utc))
    if date_to:
        conds.append(Submission.submitted_at < datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=timezone.utc))

    total = db.scalar(select(func.count()).select_from(Submission).join(prof, prof.c.sid == Submission.id, isouter=True).where(*conds))
    rows = db.execute(
        select(Submission, prof.c.pv, prof.c.pl)
        .join(prof, prof.c.sid == Submission.id, isouter=True)
        .where(*conds)
        .order_by(Submission.submitted_at.desc(), Submission.id)
        .limit(page_size).offset((page - 1) * page_size)
    ).all()
    items = [{"id": str(s.id), "profile_value": pv, "profile": pl, "submitted_at": s.submitted_at.isoformat(),
              "country": s.country, "region": s.region, "city": s.city, "is_test": s.is_test}
             for s, pv, pl in rows]
    return total or 0, items


def get_submission_detail(db: Session, submission_id):
    s = db.get(Submission, submission_id)
    if s is None:
        return None
    rows = db.execute(
        select(Question.code, Question.position, Question.text, Question.qtype, QuestionOption.value, QuestionOption.label)
        .select_from(AnswerOption)
        .join(Answer, AnswerOption.answer_id == Answer.id)
        .join(Question, Answer.question_id == Question.id)
        .join(QuestionOption, AnswerOption.option_id == QuestionOption.id)
        .where(Answer.submission_id == submission_id)
        .order_by(Question.position, QuestionOption.value)
    ).all()
    answers, index = [], {}
    for code, pos, text, qtype, value, label in rows:
        if code not in index:
            index[code] = {"code": code, "text": text, "type": qtype, "selected": []}
            answers.append(index[code])
        index[code]["selected"].append({"value": value, "label": label})
    return {"id": str(s.id), "submitted_at": s.submitted_at.isoformat(), "country": s.country, "region": s.region,
            "city": s.city, "status": s.status, "is_test": s.is_test, "answers": answers}
