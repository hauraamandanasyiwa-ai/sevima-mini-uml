from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Mahasiswa(Base):
    """Representasi tabel mahasiswa dari Modul PMB (hanya mahasiswa yang sudah
    di-approve yang memiliki NIM unik dan berhak mengisi KRS).

    Jika digabungkan ke repo Modul PMB yang sudah ada, arahkan ForeignKey
    di model KRS ke tabel pendaftar/mahasiswa ber-NIM unik milik Anda.
    """

    __tablename__ = "mahasiswa"

    nim: Mapped[str] = mapped_column(String(20), primary_key=True)
    nama: Mapped[str] = mapped_column(String(120), nullable=False)
    prodi: Mapped[str] = mapped_column(String(80), nullable=False, default="Teknik Informatika")
    status_pmb: Mapped[str] = mapped_column(String(20), nullable=False, default="approved")
