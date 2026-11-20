from datetime import date, datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Enum as SAEnum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.jalur_masuk import JalurMasuk
    from app.models.program_studi import ProgramStudi


class StatusPMB(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


status_enum = SAEnum(
    StatusPMB,
    name="status_pmb_enum",
    values_callable=lambda enum_cls: [member.value for member in enum_cls],
    native_enum=False,
    create_constraint=True,
)


class CalonMahasiswa(Base):
    __tablename__ = "calon_mahasiswa"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nama_lengkap: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(150), unique=True, index=True, nullable=False)
    phone: Mapped[str] = mapped_column(String(15), nullable=False)
    tanggal_lahir: Mapped[date] = mapped_column(Date, nullable=False)
    alamat: Mapped[str] = mapped_column(Text, nullable=False)

    program_studi_id: Mapped[int] = mapped_column(
        ForeignKey("program_studi.id", ondelete="RESTRICT"),
        nullable=False,
    )
    jalur_masuk_id: Mapped[int] = mapped_column(
        ForeignKey("jalur_masuk.id", ondelete="RESTRICT"),
        nullable=False,
    )

    status: Mapped[StatusPMB] = mapped_column(
        status_enum,
        default=StatusPMB.PENDING,
        server_default=StatusPMB.PENDING.value,
        nullable=False,
    )
    nim: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    program_studi: Mapped["ProgramStudi"] = relationship(back_populates="calon_mahasiswa")
    jalur_masuk: Mapped["JalurMasuk"] = relationship(back_populates="calon_mahasiswa")
