"""Add nim_counter table for race-condition-safe NIM generation

Revision ID: 0002_add_nim_counter
Revises: 0001_initial_pmb
Create Date: 2026-11-20 16:30:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_add_nim_counter"
down_revision: str | None = "0001_initial_pmb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "nim_counter",
        sa.Column("tahun", sa.Integer(), nullable=False),
        sa.Column("kode_prodi", sa.String(length=3), nullable=False),
        sa.Column(
            "last_number",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("tahun", "kode_prodi", name="pk_nim_counter"),
    )


def downgrade() -> None:
    op.drop_table("nim_counter")
