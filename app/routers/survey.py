from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import SubmissionIn, SubmissionOut
from app.security import client_ip, submit_limiter
from app.services import repository
from app.survey_definition import SURVEY_TITLE, survey_to_dict
from app.templating import templates

router = APIRouter()


@router.get("/", include_in_schema=False)
def home(request: Request):
    return templates.TemplateResponse(request, "index.html", {"title": SURVEY_TITLE})


@router.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "ok"}


@router.get("/api/survey")
def get_survey():
    return survey_to_dict()


@router.post("/api/survey/submissions", status_code=201, response_model=SubmissionOut)
def submit(payload: SubmissionIn, request: Request, db: Session = Depends(get_db)):
    ip = client_ip(request)
    if submit_limiter.blocked(ip):
        raise HTTPException(status_code=429, detail="Demasiados envíos desde esta conexión. Intente de nuevo en un minuto.")
    submit_limiter.hit(ip)
    sub = repository.store_submission(db, payload.model_dump())
    return SubmissionOut(id=sub.id, submitted_at=sub.submitted_at)
