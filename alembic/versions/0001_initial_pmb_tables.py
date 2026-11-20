"""Initial PMB tables: program_studi, jalur_masuk, calon_mahasiswa

Revision ID: 0001_initial_pmb
Revises:
Create Date: 2026-11-20 15:00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial_pmb"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Buat tabel referensi terlebih dahulu: program_studi
    op.create_table(
        "program_studi",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("kode", sa.String(length=3), nullable=False),
        sa.Column("nama", sa.String(length=100), nullable=False),
        sa.Column("fakultas", sa.String(length=100), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("kode", name="uq_program_studi_kode"),
    )

    # 2. Buat tabel referensi kedua: jalur_masuk
    op.create_table(
        "jalur_masuk",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("nama", sa.String(length=50), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("nama", name="uq_jalur_masuk_nama"),
    )

    # 3. Buat tabel utama: calon_mahasiswa (bergantung pada program_studi & jalur_masuk)
    op.create_table(
        "calon_mahasiswa",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("nama_lengkap", sa.String(length=150), nullable=False),
        sa.Column("email", sa.String(length=150), nullable=False),
        sa.Column("phone", sa.String(length=15), nullable=False),
        sa.Column("tanggal_lahir", sa.Date(), nullable=False),
        sa.Column("alamat", sa.Text(), nullable=False),
        sa.Column("program_studi_id", sa.Integer(), nullable=False),
        sa.Column("jalur_masuk_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "approved",
                "rejected",
                name="status_pmb_enum",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("nim", sa.String(length=20), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["program_studi_id"],
            ["program_studi.id"],
            name="fk_calon_mahasiswa_program_studi_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["jalur_masuk_id"],
            ["jalur_masuk.id"],
            name="fk_calon_mahasiswa_jalur_masuk_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_calon_mahasiswa_email"),
        sa.UniqueConstraint("nim", name="uq_calon_mahasiswa_nim"),
    )
    op.create_index(
        "ix_calon_mahasiswa_email",
        "calon_mahasiswa",
        ["email"],
        unique=True,
    )


def downgrade() -> None:
    # Urutan rollback WAJIB dibalik: hapus tabel anak dulu agar foreign key tidak error
    op.drop_index("ix_calon_mahasiswa_email", table_name="calon_mahasiswa")
    op.drop_table("calon_mahasiswa")
    op.drop_table("jalur_masuk")
    op.drop_table("program_studi")
