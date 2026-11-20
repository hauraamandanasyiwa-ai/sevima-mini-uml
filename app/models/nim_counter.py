from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class NimCounter(Base):
    """Tabel counter nomor urut NIM per kombinasi (tahun, kode_prodi).

    Digunakan bersama SELECT ... FOR UPDATE (row-level lock di MySQL/PostgreSQL)
    agar penetapan nomor urut aman terhadap race condition antar worker.
    """

    __tablename__ = "nim_counter"

    tahun: Mapped[int] = mapped_column(Integer, primary_key=True)
    kode_prodi: Mapped[str] = mapped_column(String(3), primary_key=True)
    last_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
