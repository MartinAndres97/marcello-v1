"""esquema inicial de Marcello V1

Revision ID: 0001
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "survey_versions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("code", name="uq_survey_versions_code"),
    )
    op.create_table(
        "questions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("survey_version_id", sa.Integer, sa.ForeignKey("survey_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(10), nullable=False),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("qtype", sa.String(10), nullable=False),
        sa.Column("required", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.UniqueConstraint("survey_version_id", "code", name="uq_questions_version_code"),
        sa.UniqueConstraint("survey_version_id", "position", name="uq_questions_version_position"),
        sa.CheckConstraint("qtype in ('single','multiple','likert')", name="ck_questions_qtype"),
    )
    op.create_table(
        "question_options",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("question_id", sa.Integer, sa.ForeignKey("questions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("value", sa.Integer, nullable=False),
        sa.Column("label", sa.Text, nullable=False),
        sa.UniqueConstraint("question_id", "value", name="uq_options_question_value"),
    )
    op.create_table(
        "submissions",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("survey_version_id", sa.Integer, sa.ForeignKey("survey_versions.id"), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("country", sa.String(100), nullable=False),
        sa.Column("region", sa.String(100), nullable=False),
        sa.Column("city", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="completed"),
        sa.Column("is_test", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.CheckConstraint("status in ('completed')", name="ck_submissions_status"),
    )
    op.create_index("ix_submissions_submitted_at", "submissions", ["submitted_at"])
    op.create_index("ix_submissions_is_test", "submissions", ["is_test"])
    op.create_table(
        "answers",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("submission_id", sa.Uuid, sa.ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_id", sa.Integer, sa.ForeignKey("questions.id"), nullable=False),
        sa.UniqueConstraint("submission_id", "question_id", name="uq_answers_submission_question"),
    )
    op.create_table(
        "answer_options",
        sa.Column("answer_id", sa.Integer, sa.ForeignKey("answers.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("option_id", sa.Integer, sa.ForeignKey("question_options.id"), primary_key=True),
    )
    op.create_index("ix_answer_options_option_id", "answer_options", ["option_id"])


def downgrade():
    for table in ("answer_options", "answers", "submissions", "question_options", "questions", "survey_versions"):
        op.drop_table(table)
