"""create checkpoint assessment tables

Adds the whole *Assessment* schema area of docs/database/schema.md, which had no
table until now:

    checkpoint_quizzes, checkpoint_quiz_topics, questions, question_topic_links,
    quiz_questions, quiz_attempts, quiz_attempt_answers

They arrive with the checkpoint-practice code that reads them (QZ-001 to
QZ-010), which is the ordering ADR-011 prescribes: this migration and those use
cases travel together. The area arrives **whole**, unlike the two before it,
because a quiz that cannot be attempted and an attempt that cannot be marked are
not a smaller feature but a broken one.

**Additive.** Seven CREATE TABLEs and four indexes; **no existing table is
altered** and no stored row is read, rewritten, or reinterpreted. A learner with
goals, plans, items, completions, progress, revisions, and resources keeps every
one of them untouched, and all seven new tables start empty because nothing is
written until the learner writes a question.

Departures from the approved tables, all recorded by ADR-033:

- ``questions.difficulty`` is **not created**. It is an "optional controlled
  value" with no controlled vocabulary decided anywhere, and a difficulty would
  rank one question above another, which nothing in LearnFlow does.
- ``quiz_questions.max_marks``, ``quiz_attempt_answers.awarded_marks``, and
  ``quiz_attempts.score`` / ``max_score`` are **not created**. They are a mark
  scheme, and this build has none: a result states per-question outcomes and no
  total at all. Leaving them out also leaves the one open detail
  docs/database/schema.md records -- numeric precision for score and marks
  columns -- undecided, rather than settling it in a change that would never read
  the answer.
- ``quiz_attempts.duration_seconds`` is **not created**: nothing times an
  attempt, and ``started_at`` and ``submitted_at`` already bound one.
- ``quiz_attempt_answers.feedback`` is **not created**: a question is never
  edited, only retired, so its explanation cannot drift away from an attempt
  marked against it.
- ``questions.author_learner_id`` is **added**, nullable, mirroring
  ``resources.owner_learner_id``. The schema's own *Conventions* require a
  learner identifier on learner-owned records, and the learner writes every
  question here; nullable so the curated or shared bank the table was designed
  for has somewhere to live later.
- ``questions.question_type``, both ``source_type`` columns, and every status
  column carry **all** their documented values although the application writes a
  subset. None of the unwritten values needs storage that is missing, so offering
  one later is a use-case change rather than a migration -- the argument ADR-020
  made for ``plan_items.status`` and ADR-032 for ``relationship_type``.
- Controlled columns are ``varchar(32)`` guarded by a CHECK rather than the bare
  ``text`` docs/database/schema.md describes, following its own *Conventions*,
  ADR-011's validated-text rule, and the precedent every migration since
  ``20260806_01`` has set.
- ``options``, ``expected_answer``, and ``submitted_answer`` are ``jsonb``,
  exactly as docs/database/schema.md approves.

The four indexes are the two docs/database/schema.md lists under *Required
Indexes* for this area -- ``checkpoint_quiz_topics(topic_id, checkpoint_quiz_id)``
and ``quiz_attempts(learner_id, checkpoint_quiz_id, created_at)`` -- plus two this
build's own access patterns need: one learner's askable questions, and which
questions cover a topic.

Constraint names follow the convention on ``Base.metadata``. Primary, unique, and
foreign-key conventions ignore a supplied name, so those are written out in full;
the check convention interpolates the supplied name, so a check passes only its
distinguishing suffix.

Revision ID: 20260818_01
Revises: 20260816_01
Created: 2026-08-18

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260818_01"
down_revision: str | None = "20260816_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

QUESTION_TYPES = ("multiple_choice", "multiple_select", "numeric", "short_answer")
SOURCE_TYPES = ("generated", "verified_pyq", "curated")
QUESTION_STATUSES = ("draft", "ready", "retired")
QUIZ_STATUSES = ("draft", "ready", "archived")
ATTEMPT_STATUSES = ("in_progress", "submitted", "evaluated", "abandoned")


def _in_clause(column: str, allowed: tuple[str, ...]) -> str:
    """Render the membership test the model builds for the same column.

    Written out here rather than imported: a migration describes the schema at
    one moment in history and must keep applying after the application constant
    it mirrors has moved on.
    """
    values = ", ".join(f"'{value}'" for value in allowed)
    return f"{column} IN ({values})"


def _timestamps() -> tuple[sa.Column, sa.Column]:
    """The ``created_at``/``updated_at`` pair every durable record carries."""
    return (
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def upgrade() -> None:
    """Create the seven assessment tables and their indexes."""
    op.create_table(
        "checkpoint_quizzes",
        sa.Column("id", sa.Uuid(), nullable=False),
        # Nullable, as docs/database/schema.md approves, so a reusable quiz has
        # somewhere to live later. Nothing writes an ownerless row today.
        sa.Column("learner_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_checkpoint_quizzes"),
        sa.ForeignKeyConstraint(
            ["learner_id"], ["learners.id"], name="fk_checkpoint_quizzes_learner_id_learners"
        ),
        sa.CheckConstraint(_in_clause("source_type", SOURCE_TYPES), name="source_type_is_known"),
        sa.CheckConstraint(_in_clause("status", QUIZ_STATUSES), name="status_is_known"),
    )

    op.create_table(
        "checkpoint_quiz_topics",
        sa.Column("checkpoint_quiz_id", sa.Uuid(), nullable=False),
        sa.Column("topic_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        # The approved primary key, which is also the approved unique constraint
        # on the pair: ADR-008 requires the quiz-to-topic link to be unique, and
        # a composite primary key states that once.
        sa.PrimaryKeyConstraint("checkpoint_quiz_id", "topic_id", name="pk_checkpoint_quiz_topics"),
        sa.ForeignKeyConstraint(
            ["checkpoint_quiz_id"],
            ["checkpoint_quizzes.id"],
            name="fk_checkpoint_quiz_topics_checkpoint_quiz_id_checkpoint_quizzes",
        ),
        # Not a cascade. Curriculum rows are reference data that learner records
        # reference, and docs/database/schema.md forbids deleting one casually.
        sa.ForeignKeyConstraint(
            ["topic_id"], ["topics.id"], name="fk_checkpoint_quiz_topics_topic_id_topics"
        ),
    )
    op.create_index(
        "ix_checkpoint_quiz_topics_topic_id_checkpoint_quiz_id",
        "checkpoint_quiz_topics",
        ["topic_id", "checkpoint_quiz_id"],
    )

    op.create_table(
        "questions",
        sa.Column("id", sa.Uuid(), nullable=False),
        # Added beyond the approved shape; see the module docstring.
        sa.Column("author_learner_id", sa.Uuid(), nullable=True),
        sa.Column("question_type", sa.String(length=32), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("options", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("expected_answer", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_questions"),
        sa.ForeignKeyConstraint(
            ["author_learner_id"], ["learners.id"], name="fk_questions_author_learner_id_learners"
        ),
        sa.CheckConstraint(
            _in_clause("question_type", QUESTION_TYPES), name="question_type_is_known"
        ),
        sa.CheckConstraint(_in_clause("source_type", SOURCE_TYPES), name="source_type_is_known"),
        sa.CheckConstraint(_in_clause("status", QUESTION_STATUSES), name="status_is_known"),
    )
    op.create_index(
        "ix_questions_author_learner_id_status", "questions", ["author_learner_id", "status"]
    )

    op.create_table(
        "question_topic_links",
        sa.Column("question_id", sa.Uuid(), nullable=False),
        sa.Column("topic_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("question_id", "topic_id", name="pk_question_topic_links"),
        sa.ForeignKeyConstraint(
            ["question_id"], ["questions.id"], name="fk_question_topic_links_question_id_questions"
        ),
        sa.ForeignKeyConstraint(
            ["topic_id"], ["topics.id"], name="fk_question_topic_links_topic_id_topics"
        ),
    )
    op.create_index(
        "ix_question_topic_links_topic_id_question_id",
        "question_topic_links",
        ["topic_id", "question_id"],
    )

    op.create_table(
        "quiz_questions",
        sa.Column("checkpoint_quiz_id", sa.Uuid(), nullable=False),
        sa.Column("question_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("checkpoint_quiz_id", "question_id", name="pk_quiz_questions"),
        sa.ForeignKeyConstraint(
            ["checkpoint_quiz_id"],
            ["checkpoint_quizzes.id"],
            name="fk_quiz_questions_checkpoint_quiz_id_checkpoint_quizzes",
        ),
        sa.ForeignKeyConstraint(
            ["question_id"], ["questions.id"], name="fk_quiz_questions_question_id_questions"
        ),
        # docs/database/schema.md: no two questions share a place in one quiz.
        sa.UniqueConstraint(
            "checkpoint_quiz_id", "position", name="uq_quiz_questions_checkpoint_quiz_id_position"
        ),
        # The approved `max_marks > 0` guards a column this migration does not
        # create. What survives of it is the guard on the column that replaces
        # its role: a position counts from 1.
        sa.CheckConstraint("position >= 1", name="position_is_positive"),
    )

    op.create_table(
        "quiz_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("learner_id", sa.Uuid(), nullable=False),
        sa.Column("checkpoint_quiz_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_quiz_attempts"),
        sa.ForeignKeyConstraint(
            ["learner_id"], ["learners.id"], name="fk_quiz_attempts_learner_id_learners"
        ),
        sa.ForeignKeyConstraint(
            ["checkpoint_quiz_id"],
            ["checkpoint_quizzes.id"],
            name="fk_quiz_attempts_checkpoint_quiz_id_checkpoint_quizzes",
        ),
        sa.CheckConstraint(_in_clause("status", ATTEMPT_STATUSES), name="status_is_known"),
    )
    op.create_index(
        "ix_quiz_attempts_learner_id_checkpoint_quiz_id_created_at",
        "quiz_attempts",
        ["learner_id", "checkpoint_quiz_id", "created_at"],
    )

    op.create_table(
        "quiz_attempt_answers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("quiz_attempt_id", sa.Uuid(), nullable=False),
        sa.Column("question_id", sa.Uuid(), nullable=False),
        sa.Column("submitted_answer", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        # Nullable, and deliberately so: null is a question the learner left
        # alone. An unanswered question is not a wrong one.
        sa.Column("is_correct", sa.Boolean(), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_quiz_attempt_answers"),
        sa.ForeignKeyConstraint(
            ["quiz_attempt_id"],
            ["quiz_attempts.id"],
            name="fk_quiz_attempt_answers_quiz_attempt_id_quiz_attempts",
        ),
        sa.ForeignKeyConstraint(
            ["question_id"], ["questions.id"], name="fk_quiz_attempt_answers_question_id_questions"
        ),
        sa.UniqueConstraint(
            "quiz_attempt_id",
            "question_id",
            name="uq_quiz_attempt_answers_quiz_attempt_id_question_id",
        ),
    )


def downgrade() -> None:
    """Drop all seven tables, and their indexes with them.

    Dropped children first, so no table is removed while another still references
    it. Each index is dropped explicitly before its table for symmetry with the
    upgrade. No constraint is named: dropping a table takes its checks with it,
    which also keeps this clear of the ``ck`` naming convention that bit revision
    ``20260806_02``. See docs/database/migrations.md.
    """
    op.drop_table("quiz_attempt_answers")
    op.drop_index(
        "ix_quiz_attempts_learner_id_checkpoint_quiz_id_created_at", table_name="quiz_attempts"
    )
    op.drop_table("quiz_attempts")
    op.drop_table("quiz_questions")
    op.drop_index("ix_question_topic_links_topic_id_question_id", table_name="question_topic_links")
    op.drop_table("question_topic_links")
    op.drop_index("ix_questions_author_learner_id_status", table_name="questions")
    op.drop_table("questions")
    op.drop_index(
        "ix_checkpoint_quiz_topics_topic_id_checkpoint_quiz_id",
        table_name="checkpoint_quiz_topics",
    )
    op.drop_table("checkpoint_quiz_topics")
    op.drop_table("checkpoint_quizzes")
