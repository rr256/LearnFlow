"""add topic code unique constraint

Makes `(subject_id, code)` unique on `topics`, so a topic code identifies exactly
one topic within its subject at any depth.

`topics.code` is optional and the curated GATE CSE curriculum leaves it NULL
throughout, so this constraint keeps PostgreSQL's default NULLS DISTINCT
behaviour: every NULL code stays distinct and only real duplicate codes are
rejected. That is deliberately the opposite of
`uq_topics_subject_id_parent_topic_id_name`, created in `20260731_01`, which
declares NULLS NOT DISTINCT precisely so a NULL parent cannot escape the rule.
The two constraints want opposite things from NULL and say so explicitly.

Additive and safe on populated tables: it creates no column and rejects no row
that satisfies it. It would fail on a database that already holds duplicate
topic codes within one subject; none can exist, because the only writer is the
curriculum seed and it refuses such a file.

Revision ID: 20260731_02
Revises: 20260731_01
Created: 2026-07-31

"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260731_02"
down_revision: str | None = "20260731_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_topics_subject_id_code",
        "topics",
        ["subject_id", "code"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_topics_subject_id_code", "topics", type_="unique")
