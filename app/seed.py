from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Question, QuestionOption, SurveyVersion
from app.survey_definition import QUESTIONS, SURVEY_CODE, SURVEY_TITLE


def seed_survey(db: Session) -> None:
    """Crea la versión v1 del cuestionario si no existe (idempotente; nunca modifica una existente)."""
    if db.scalar(select(SurveyVersion.id).where(SurveyVersion.code == SURVEY_CODE)):
        return
    sv = SurveyVersion(code=SURVEY_CODE, title=SURVEY_TITLE, is_active=True)
    db.add(sv)
    db.flush()
    for q in QUESTIONS:
        question = Question(survey_version_id=sv.id, code=q.code, position=q.position, text=q.text,
                            qtype=q.qtype, required=True)
        db.add(question)
        db.flush()
        db.add_all([QuestionOption(question_id=question.id, value=i, label=label)
                    for i, label in enumerate(q.options, start=1)])
    db.commit()
