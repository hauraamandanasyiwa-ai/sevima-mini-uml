from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.calon_mahasiswa import CalonMahasiswa


class ProgramStudi(Base):
    __tablename__ = "program_studi"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    kode: Mapped[str] = mapped_column(String(3), unique=True, nullable=False)
    nama: Mapped[str] = mapped_column(String(100), nullable=False)
    fakultas: Mapped[str] = mapped_column(String(100), nullable=False)

    calon_mahasiswa: Mapped[list["CalonMahasiswa"]] = relationship(
        back_populates="program_studi"
    )
