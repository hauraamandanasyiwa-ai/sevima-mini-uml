from datetime import time

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Ruangan(Base):
    """Tabel ruangan kuliah (kode sebagai primary key alami, mis. 'A101', 'LAB1')."""

    __tablename__ = "ruangan"
    __table_args__ = (
        CheckConstraint("kapasitas >= 1", name="ck_ruangan_kapasitas_pos"),
    )

    kode: Mapped[str] = mapped_column(String(16), primary_key=True)
    nama: Mapped[str] = mapped_column(String(100), nullable=False)
    kapasitas: Mapped[int] = mapped_column(Integer, nullable=False)

    def __repr__(self) -> str:
        return f"<Ruangan {self.kode} ({self.nama}, cap={self.kapasitas})>"


class Dosen(Base):
    """Tabel dosen pengampu mata kuliah dengan NIDN unik."""

    __tablename__ = "dosen"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nidn: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    nama: Mapped[str] = mapped_column(String(120), nullable=False)

    def __repr__(self) -> str:
        return f"<Dosen id={self.id} nidn={self.nidn} nama={self.nama}>"


class Kelas(Base):
    """Kelas paralel dari sebuah mata kuliah (mis. Basis Data Kelas A & Kelas B)."""

    __tablename__ = "kelas"
    __table_args__ = (
        UniqueConstraint("kode_mk", "nama_kelas", "semester", name="uq_kelas_mk_nama_sem"),
        CheckConstraint("kuota >= 1", name="ck_kelas_kuota_pos"),
        CheckConstraint("LENGTH(semester) = 5", name="ck_kelas_semester_len"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kode_mk: Mapped[str] = mapped_column(
        String(16),
        ForeignKey("mata_kuliah.kode_mk", ondelete="RESTRICT"),
        nullable=False,
    )
    nama_kelas: Mapped[str] = mapped_column(String(16), nullable=False)
    kuota: Mapped[int] = mapped_column(Integer, nullable=False)
    semester: Mapped[str] = mapped_column(String(5), nullable=False)

    mata_kuliah = relationship("MataKuliah", lazy="joined")
    jadwals: Mapped[list["Jadwal"]] = relationship(
        "Jadwal",
        back_populates="kelas",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Kelas id={self.id} {self.kode_mk}-{self.nama_kelas} ({self.semester}, kuota={self.kuota})>"


class Jadwal(Base):
    """Satu pertemuan mingguan yang mengikat kelas, ruangan, dosen, hari, dan slot waktu.

    Dipisah dari Kelas karena satu kelas bisa bertemu lebih dari sekali seminggu
    (mis. teori Senin di A101 dan praktikum Kamis di LAB1).

    Dua indeks gabungan dirancang dari pertanyaan tersering:
    - idx_jadwal_hari_ruangan: jadwal apa saja di ruangan ini pada hari ini?
    - idx_jadwal_hari_dosen  : jadwal apa saja milik dosen ini pada hari ini?
    """

    __tablename__ = "jadwal"
    __table_args__ = (
        CheckConstraint("hari >= 1 AND hari <= 6", name="ck_jadwal_hari_range"),
        CheckConstraint("jam_mulai < jam_selesai", name="ck_jadwal_jam_valid"),
        Index("idx_jadwal_hari_ruangan", "hari", "ruangan_kode"),
        Index("idx_jadwal_hari_dosen", "hari", "dosen_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kelas_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("kelas.id", ondelete="CASCADE"),
        nullable=False,
    )
    ruangan_kode: Mapped[str] = mapped_column(
        String(16),
        ForeignKey("ruangan.kode", ondelete="RESTRICT"),
        nullable=False,
    )
    dosen_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("dosen.id", ondelete="RESTRICT"),
        nullable=False,
    )
    # 1 = Senin .. 6 = Sabtu
    hari: Mapped[int] = mapped_column(Integer, nullable=False)
    # Bertipe Time (BUKAN string!) untuk mencegah bug perbandingan teks '9:00' > '10:00'
    jam_mulai: Mapped[time] = mapped_column(Time, nullable=False)
    jam_selesai: Mapped[time] = mapped_column(Time, nullable=False)

    kelas: Mapped["Kelas"] = relationship("Kelas", back_populates="jadwals", lazy="joined")
    ruangan: Mapped["Ruangan"] = relationship("Ruangan", lazy="joined")
    dosen: Mapped["Dosen"] = relationship("Dosen", lazy="joined")

    def __repr__(self) -> str:
        return (
            f"<Jadwal id={self.id} kelas={self.kelas_id} ruang={self.ruangan_kode} "
            f"dosen={self.dosen_id} hari={self.hari} {self.jam_mulai}-{self.jam_selesai}>"
        )
