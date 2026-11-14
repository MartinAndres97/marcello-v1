"""Modelo relacional normalizado.

survey_versions 1─n questions 1─n question_options
submissions 1─n answers (una por pregunta) 1─n answer_options (opciones elegidas)
Las respuestas únicas, Likert y múltiples usan la MISMA estructura: no hay datos duplicados.
"""
import uuid
from datetime import datetime

from sqlalchemy import (Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text,
                        UniqueConstraint, Uuid, func)
from sqlalchemy import text as sql_text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class SurveyVersion(Base):
    __tablename__ = "survey_versions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sql_text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Question(Base):
    __tablename__ = "questions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    survey_version_id: Mapped[int] = mapped_column(ForeignKey("survey_versions.id", ondelete="CASCADE"), nullable=False)
    code: Mapped[str] = mapped_column(String(10), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    qtype: Mapped[str] = mapped_column(String(10), nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sql_text("true"))
    __table_args__ = (
        UniqueConstraint("survey_version_id", "code", name="uq_questions_version_code"),
        UniqueConstraint("survey_version_id", "position", name="uq_questions_version_position"),
        CheckConstraint("qtype in ('single','multiple','likert')", name="ck_questions_qtype"),
    )


class QuestionOption(Base):
    __tablename__ = "question_options"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    value: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    __table_args__ = (UniqueConstraint("question_id", "value", name="uq_options_question_value"),)


class Submission(Base):
    __tablename__ = "submissions"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    survey_version_id: Mapped[int] = mapped_column(ForeignKey("survey_versions.id"), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    region: Mapped[str] = mapped_column(String(100), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="completed")
    # Marca los registros ficticios de prueba para que nunca se mezclen con los reales.
    is_test: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sql_text("false"))
    answers: Mapped[list["Answer"]] = relationship(back_populates="submission", cascade="all, delete-orphan",
                                                   passive_deletes=True)
    __table_args__ = (
        CheckConstraint("status in ('completed')", name="ck_submissions_status"),
        Index("ix_submissions_submitted_at", "submitted_at"),
        Index("ix_submissions_is_test", "is_test"),
    )


class Answer(Base):
    __tablename__ = "answers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    submission_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), nullable=False)
    submission: Mapped["Submission"] = relationship(back_populates="answers")
    selected: Mapped[list["AnswerOption"]] = relationship(cascade="all, delete-orphan", passive_deletes=True)
    __table_args__ = (UniqueConstraint("submission_id", "question_id", name="uq_answers_submission_question"),)


class AnswerOption(Base):
    __tablename__ = "answer_options"
    answer_id: Mapped[int] = mapped_column(ForeignKey("answers.id", ondelete="CASCADE"), primary_key=True)
    option_id: Mapped[int] = mapped_column(ForeignKey("question_options.id"), primary_key=True)
    __table_args__ = (Index("ix_answer_options_option_id", "option_id"),)
