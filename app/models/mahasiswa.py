from typing import Optional

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Mahasiswa(Base):
    """Representasi tabel mahasiswa dari Modul PMB (hanya mahasiswa yang sudah
    di-approve yang memiliki NIM unik dan berhak mengisi KRS).

    Menyimpan `dosen_pa_id` sebagai dosen pembimbing akademik bawaan mahasiswa.
    """

    __tablename__ = "mahasiswa"

    nim: Mapped[str] = mapped_column(String(20), primary_key=True)
    nama: Mapped[str] = mapped_column(String(120), nullable=False)
    prodi: Mapped[str] = mapped_column(String(80), nullable=False, default="Teknik Informatika")
    status_pmb: Mapped[str] = mapped_column(String(20), nullable=False, default="approved")
    dosen_pa_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
