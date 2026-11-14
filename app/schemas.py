import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator

from app.survey_definition import validate_answers

_LOCATION_RE = re.compile(r"[\w .,'’()/\-]+")
NOT_REPORTED = "No informado"  # la encuesta ya no pregunta ubicación


class SubmissionIn(BaseModel):
    # extra="forbid": cualquier campo no previsto (p. ej. email, nombre, gps) se rechaza.
    model_config = ConfigDict(extra="forbid")

    country: str = NOT_REPORTED
    region: str = NOT_REPORTED
    city: str = NOT_REPORTED
    answers: dict[str, list[StrictInt]]

    @field_validator("country", "region", "city")
    @classmethod
    def _clean_location(cls, v: str) -> str:
        v = " ".join(v.split())
        if not 2 <= len(v) <= 100:
            raise ValueError("debe tener entre 2 y 100 caracteres")
        if not v[0].isalnum() or not _LOCATION_RE.fullmatch(v):
            raise ValueError("contiene caracteres no permitidos")
        return v

    @model_validator(mode="after")
    def _check_answers(self):
        clean, errors = validate_answers(self.answers)
        if errors:
            raise ValueError("; ".join(f"{k}: {msg}" for k, msg in sorted(errors.items())))
        self.answers = clean
        return self


class SubmissionOut(BaseModel):
    id: uuid.UUID
    submitted_at: datetime


class LoginIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(max_length=100)
    password: str = Field(max_length=128)
