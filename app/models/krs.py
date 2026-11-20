import enum
from datetime import datetime, time, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Table,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.exceptions import TransitionError

# Tabel perantara self-referencing many-to-many untuk prasyarat mata kuliah.
prerequisites = Table(
    "prerequisites",
    Base.metadata,
    Column(
        "kode_mk",
        String(16),
        ForeignKey("mata_kuliah.kode_mk", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "kode_prasyarat",
        String(16),
        ForeignKey("mata_kuliah.kode_mk", ondelete="CASCADE"),
        primary_key=True,
    ),
    CheckConstraint("kode_mk <> kode_prasyarat", name="ck_prereq_not_self"),
)


class KRSStatus(str, enum.Enum):
    """Empat state resmi Kartu Rencana Studi (State Machine).

    Satu kolom Enum mencegah kombinasi mustahil (seperti is_approved=True namun
    is_submitted=False) yang sering muncul pada desain banyak kolom boolean.
    """

    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REVISION = "revision"


class KRSAktor(str, enum.Enum):
    """Peran aktor pemicu transisi state KRS."""

    MAHASISWA = "mahasiswa"
    DOSEN_PA = "dosen_pa"


EDITABLE_KRS_STATUSES: frozenset[KRSStatus] = frozenset(
    {KRSStatus.DRAFT, KRSStatus.REVISION}
)

# Tabel Transisi State Machine KRS:
# Kunci  : (status_saat_ini, aktor)
# Nilai  : himpunan status tujuan yang sah
#
# - DRAFT    + mahasiswa -> {SUBMITTED}
# - SUBMITTED + dosen_pa -> {APPROVED, REVISION}
# - REVISION + mahasiswa -> {SUBMITTED}
# - APPROVED adalah terminal state (tidak ada transisi keluar).
# - DRAFT -> APPROVED dan REVISION -> APPROVED secara eksplisit TIDAK ADA.
KRS_TRANSITIONS: dict[tuple[KRSStatus, str], frozenset[KRSStatus]] = {
    (KRSStatus.DRAFT, KRSAktor.MAHASISWA.value): frozenset({KRSStatus.SUBMITTED}),
    (KRSStatus.SUBMITTED, KRSAktor.DOSEN_PA.value): frozenset(
        {KRSStatus.APPROVED, KRSStatus.REVISION}
    ),
    (KRSStatus.REVISION, KRSAktor.MAHASISWA.value): frozenset({KRSStatus.SUBMITTED}),
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MataKuliah(Base):
    """Tabel 1: Menyimpan data mata kuliah serta jadwal."""

    __tablename__ = "mata_kuliah"
    __table_args__ = (
        CheckConstraint("sks >= 1 AND sks <= 4", name="ck_mk_sks_range"),
        CheckConstraint("hari >= 1 AND hari <= 6", name="ck_mk_hari_range"),
        CheckConstraint("jam_mulai < jam_selesai", name="ck_mk_jam_valid"),
    )

    kode_mk: Mapped[str] = mapped_column(String(16), primary_key=True)
    nama: Mapped[str] = mapped_column(String(120), nullable=False)
    sks: Mapped[int] = mapped_column(Integer, nullable=False)
    # 1 = Senin, 2 = Selasa, 3 = Rabu, 4 = Kamis, 5 = Jumat, 6 = Sabtu
    hari: Mapped[int] = mapped_column(Integer, nullable=False)
    jam_mulai: Mapped[time] = mapped_column(Time, nullable=False)
    jam_selesai: Mapped[time] = mapped_column(Time, nullable=False)
    # Flag prioritas untuk Challenge Opsional KRS Recommendation AI
    is_wajib: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    prasyarat: Mapped[list["MataKuliah"]] = relationship(
        "MataKuliah",
        secondary=prerequisites,
        primaryjoin="MataKuliah.kode_mk == prerequisites.c.kode_mk",
        secondaryjoin="MataKuliah.kode_mk == prerequisites.c.kode_prasyarat",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<MataKuliah {self.kode_mk} - {self.nama} ({self.sks} SKS)>"


class KRS(Base):
    """Tabel 2: Satu kartu rencana studi milik satu mahasiswa pada satu semester.

    Dilengkapi:
    - Enkapsulasi State Machine melalui `check_transition()` & `transition()`.
    - Optimistic Locking melalui kolom `version` (`version_id_col`) untuk
      mencegah *stale screen* saat dosen PA menyetujui KRS yang sedang diedit.
    """

    __tablename__ = "krs"
    __table_args__ = (
        UniqueConstraint("nim", "semester", name="uq_krs_nim_semester"),
        CheckConstraint("LENGTH(semester) = 5", name="ck_krs_semester_len"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nim: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("mahasiswa.nim", ondelete="RESTRICT"),
        nullable=False,
    )
    semester: Mapped[str] = mapped_column(String(5), nullable=False)
    status: Mapped[KRSStatus] = mapped_column(
        Enum(KRSStatus, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=KRSStatus.DRAFT,
    )
    dosen_pa_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revision_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )
    # Kolom versi untuk Optimistic Locking (otomatis dinaikkan SQLAlchemy setiap UPDATE)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    __mapper_args__ = {
        "version_id_col": version,
    }

    details: Mapped[list["KRSDetail"]] = relationship(
        "KRSDetail",
        back_populates="krs",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    approval_logs: Mapped[list["KRSApprovalLog"]] = relationship(
        "KRSApprovalLog",
        back_populates="krs",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def check_transition(self, target: KRSStatus, actor: str | KRSAktor) -> None:
        """Memeriksa apakah transisi `self.status -> target` oleh `actor` sah.

        Dipisah dari `transition()` agar service seperti `submit_krs` bisa
        memeriksa status lebih dulu sebelum menjalankan validasi yang mahal.
        """
        actor_key = actor.value if isinstance(actor, KRSAktor) else actor
        allowed_targets = KRS_TRANSITIONS.get((self.status, actor_key), frozenset())
        if target not in allowed_targets:
            raise TransitionError(
                f"Transisi tidak diizinkan: {self.status.value} ke {target.value} "
                f"oleh aktor '{actor_key}'."
            )

    def transition(self, target: KRSStatus, actor: str | KRSAktor) -> None:
        """Satu-satunya method yang diizinkan mengubah `self.status` (enkapsulasi).

        Tidak ada service maupun endpoint yang boleh menulis `krs.status = ...`
        secara langsung.
        """
        self.check_transition(target, actor)
        self.status = target
        self.touch()

    def touch(self) -> None:
        """Menyentuh `updated_at` agar SQLAlchemy ikut menaikkan `version`
        walaupun perubahan hanya terjadi pada tabel anak (`krs_detail`).
        """
        self.updated_at = _utcnow()

    def __repr__(self) -> str:
        return (
            f"<KRS id={self.id} nim={self.nim} semester={self.semester} "
            f"status={self.status.value} v={self.version}>"
        )


class KRSDetail(Base):
    """Tabel 3: Baris mata kuliah di dalam satu KRS."""

    __tablename__ = "krs_detail"
    __table_args__ = (
        UniqueConstraint("krs_id", "kode_mk", name="uq_krs_detail_krs_mk"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    krs_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("krs.id", ondelete="CASCADE"),
        nullable=False,
    )
    kode_mk: Mapped[str] = mapped_column(
        String(16),
        ForeignKey("mata_kuliah.kode_mk", ondelete="RESTRICT"),
        nullable=False,
    )
    # Kolom opsional menuju Kelas (Minggu 7) untuk menghitung jumlah peserta terdaftar
    # pada capacity check; integrasi penuh dengan KRS dituntaskan di Minggu 8.
    kelas_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("kelas.id", ondelete="SET NULL"),
        nullable=True,
    )
    nilai: Mapped[Optional[str]] = mapped_column(String(2), nullable=True)

    krs: Mapped["KRS"] = relationship("KRS", back_populates="details")
    mata_kuliah: Mapped["MataKuliah"] = relationship("MataKuliah", lazy="joined")

    def __repr__(self) -> str:
        return f"<KRSDetail krs_id={self.krs_id} kode_mk={self.kode_mk} nilai={self.nilai}>"


class KRSApprovalLog(Base):
    """Log audit perubahan status KRS (disimpan atomik di dalam transaksi approve/revise)."""

    __tablename__ = "krs_approval_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    krs_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("krs.id", ondelete="CASCADE"),
        nullable=False,
    )
    action: Mapped[str] = mapped_column(String(20), nullable=False)  # submit, approve, revise
    actor_id: Mapped[str] = mapped_column(String(32), nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    krs: Mapped["KRS"] = relationship("KRS", back_populates="approval_logs")


class Notifikasi(Base):
    """Catatan notifikasi yang disimpan di database dalam transaksi yang sama.

    Notifikasi TIDAK dikirim sebagai email di tengah transaksi (karena email
    tidak bisa di-rollback). Pengiriman eksternal dilakukan setelah commit
    melalui Observer Pattern pada Minggu 7.
    """

    __tablename__ = "notifikasi"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nim: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("mahasiswa.nim", ondelete="CASCADE"),
        nullable=False,
    )
    krs_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("krs.id", ondelete="CASCADE"),
        nullable=False,
    )
    judul: Mapped[str] = mapped_column(String(120), nullable=False)
    pesan: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )


class SkalaNilai(Base):
    """Tabel pemetaan nilai huruf ke bobot numerik."""

    __tablename__ = "skala_nilai"

    huruf: Mapped[str] = mapped_column(String(2), primary_key=True)
    bobot: Mapped[Decimal] = mapped_column(Numeric(3, 2), nullable=False)


DEFAULT_SKALA_NILAI: dict[str, Decimal] = {
    "A": Decimal("4.00"),
    "A-": Decimal("3.70"),
    "B+": Decimal("3.30"),
    "B": Decimal("3.00"),
    "B-": Decimal("2.70"),
    "C+": Decimal("2.30"),
    "C": Decimal("2.00"),
    "D": Decimal("1.00"),
    "E": Decimal("0.00"),
}
