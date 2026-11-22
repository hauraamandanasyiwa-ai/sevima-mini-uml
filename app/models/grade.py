from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Grade(Base):
    """Tabel nilai mahasiswa per mata kuliah per semester (Modul Nilai & Transkrip).

    Menyimpan huruf nilai, konversi angka (Decimal), serta persentase presensi
    sebagai dasar penegakan business rule presensi minimal 75%.
    """

    __tablename__ = "grades"
    __table_args__ = (
        UniqueConstraint("nim", "kode_mk", "semester", name="uq_grades_nim_mk_sem"),
        CheckConstraint("LENGTH(semester) = 5", name="ck_grades_semester_len"),
        CheckConstraint(
            "presensi_persen >= 0 AND presensi_persen <= 100",
            name="ck_grades_presensi_range",
        ),
        CheckConstraint(
            "nilai_angka >= 0 AND nilai_angka <= 4",
            name="ck_grades_angka_range",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nim: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("mahasiswa.nim", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    kode_mk: Mapped[str] = mapped_column(
        String(16),
        ForeignKey("mata_kuliah.kode_mk", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    semester: Mapped[str] = mapped_column(String(5), nullable=False, index=True)
    nilai_huruf: Mapped[str] = mapped_column(String(2), nullable=False)
    nilai_angka: Mapped[Decimal] = mapped_column(Numeric(3, 2), nullable=False)
    presensi_persen: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("100.00")
    )
    updated_by: Mapped[str] = mapped_column(String(64), nullable=False, default="system")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    mahasiswa = relationship("Mahasiswa", lazy="joined")
    mata_kuliah = relationship("MataKuliah", lazy="joined")
    history: Mapped[list["GradeHistory"]] = relationship(
        "GradeHistory",
        back_populates="grade",
        cascade="all, delete-orphan",
        order_by="GradeHistory.changed_at.desc()",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<Grade id={self.id} nim={self.nim} mk={self.kode_mk} "
            f"sem={self.semester} nilai={self.nilai_huruf} ({self.nilai_angka})>"
        )


class GradeHistory(Base):
    """Tabel audit trail perubahan nilai (Step 3: grade_history).

    Setiap perubahan nilai pada tabel `grades` wajib menyisipkan satu baris
    di sini dalam transaksi yang sama untuk merekam siapa mengubah, kapan,
    nilai lama -> baru, serta alasannya.
    """

    __tablename__ = "grade_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    grade_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("grades.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    old_value: Mapped[str] = mapped_column(String(2), nullable=False)
    new_value: Mapped[str] = mapped_column(String(2), nullable=False)
    changed_by: Mapped[str] = mapped_column(String(64), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=False)

    grade: Mapped["Grade"] = relationship("Grade", back_populates="history")

    def __repr__(self) -> str:
        return (
            f"<GradeHistory id={self.id} grade_id={self.grade_id} "
            f"{self.old_value}->{self.new_value} by={self.changed_by}>"
        )
