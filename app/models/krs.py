import enum
from datetime import time
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    Column,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Table,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# Tabel perantara self-referencing many-to-many untuk prasyarat mata kuliah.
# Didefinisikan sebagai objek Table (bukan class ORM tersendiri) karena hanya
# menyimpan pasangan kunci. Composite PK mencegah pasangan prasyarat duplikat
# sekaligus otomatis menyediakan indeks pada kode_mk.
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
    """Status Kartu Rencana Studi.

    Minggu 5: hanya DRAFT dan REVISION yang mengizinkan perubahan mata kuliah.
    Minggu 6: transisi penuh (State Machine) dari DRAFT -> SUBMITTED -> APPROVED/REVISION.
    """

    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REVISION = "revision"


EDITABLE_KRS_STATUSES: frozenset[KRSStatus] = frozenset(
    {KRSStatus.DRAFT, KRSStatus.REVISION}
)


class MataKuliah(Base):
    """Tabel 1: Menyimpan data mata kuliah serta jadwal (penyederhanaan 1 MK = 1 kelas
    sebelum modul jadwal di minggu ke-7).
    """

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

    # Self-referencing many-to-many:
    # primaryjoin menghubungkan MK saat ini ke kolom kode_mk.
    # secondaryjoin menghubungkan kolom kode_prasyarat ke MK prasyaratnya.
    # Contoh: struktur_data.prasyarat == [algoritma]
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

    Status dan dosen PA disimpan di tingkat kartu agar tidak mungkin setengah
    mata kuliah berstatus approved dan setengahnya draft.
    """

    __tablename__ = "krs"
    __table_args__ = (
        # Satu mahasiswa hanya boleh punya 1 KRS per semester.
        # Sekaligus otomatis membuat composite index (nim, semester):
        # equality column (nim) lebih dulu, range column (semester) belakangan.
        UniqueConstraint("nim", "semester", name="uq_krs_nim_semester"),
        CheckConstraint("LENGTH(semester) = 5", name="ck_krs_semester_len"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nim: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("mahasiswa.nim", ondelete="RESTRICT"),
        nullable=False,
    )
    # Format fixed-length 5 karakter (contoh: '20251' = Ganjil 2025, '20252' = Genap 2025)
    # agar perbandingan semester sebelumnya (semester < :semester) valid secara leksikografis.
    semester: Mapped[str] = mapped_column(String(5), nullable=False)
    status: Mapped[KRSStatus] = mapped_column(
        Enum(KRSStatus, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=KRSStatus.DRAFT,
    )
    dosen_pa_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    # cascade="all, delete-orphan" memastikan detail yang dilepas benar-benar terhapus di DB.
    details: Mapped[list["KRSDetail"]] = relationship(
        "KRSDetail",
        back_populates="krs",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<KRS id={self.id} nim={self.nim} semester={self.semester} status={self.status.value}>"


class KRSDetail(Base):
    """Tabel 3: Baris mata kuliah di dalam satu KRS.

    Kolom nilai boleh NULL saat KRS sedang diambil, dan baru diisi setelah
    semester selesai sebagai bukti kelulusan prasyarat untuk semester berikutnya.
    """

    __tablename__ = "krs_detail"
    __table_args__ = (
        # Lapis penjaga terakhir di level database untuk aturan anti double enrollment,
        # sekaligus otomatis menyediakan composite index (krs_id, kode_mk).
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
    nilai: Mapped[Optional[str]] = mapped_column(String(2), nullable=True)

    krs: Mapped["KRS"] = relationship("KRS", back_populates="details")
    mata_kuliah: Mapped["MataKuliah"] = relationship("MataKuliah", lazy="joined")

    def __repr__(self) -> str:
        return f"<KRSDetail krs_id={self.krs_id} kode_mk={self.kode_mk} nilai={self.nilai}>"


class SkalaNilai(Base):
    """Tabel pemetaan nilai huruf ke bobot numerik.

    Menghindari jebakan perbandingan string (di mana 'B' < 'C' dan 'D' > 'C'
    sehingga `nilai >= 'C'` meloloskan D/E dan menolak A/B).
    """

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
