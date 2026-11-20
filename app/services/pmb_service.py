from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.calon_mahasiswa import CalonMahasiswa, StatusPMB
from app.models.jalur_masuk import JalurMasuk
from app.models.program_studi import ProgramStudi
from app.schemas.pmb import RegisterRequest


class EmailAlreadyRegisteredError(Exception):
    """Dilempar ketika email pendaftar sudah terdaftar di sistem."""


class InvalidReferenceError(Exception):
    """Dilempar ketika program studi atau jalur masuk tidak ditemukan."""


class PMBService:
    """Lapisan aturan bisnis modul Penerimaan Mahasiswa Baru (PMB)."""

    @staticmethod
    def register(db: Session, data: RegisterRequest) -> CalonMahasiswa:
        normalized_email = str(data.email).strip().lower()

        # 1. Cek apakah email sudah pernah terdaftar
        existing = db.scalar(
            select(CalonMahasiswa).where(CalonMahasiswa.email == normalized_email)
        )
        if existing is not None:
            raise EmailAlreadyRegisteredError("Email sudah terdaftar")

        # 2. Pastikan program studi dan jalur masuk benar-benar ada
        prodi = db.get(ProgramStudi, data.program_studi_id)
        if prodi is None:
            raise InvalidReferenceError("Program studi tidak ditemukan")

        jalur = db.get(JalurMasuk, data.jalur_masuk_id)
        if jalur is None:
            raise InvalidReferenceError("Jalur masuk tidak ditemukan")

        # 3. Buat objek CalonMahasiswa (objek -> baris tabel) dengan status default pending
        calon = CalonMahasiswa(
            nama_lengkap=data.nama_lengkap.strip(),
            email=normalized_email,
            phone=data.phone.strip(),
            tanggal_lahir=data.tanggal_lahir,
            alamat=data.alamat.strip(),
            program_studi_id=data.program_studi_id,
            jalur_masuk_id=data.jalur_masuk_id,
            status=StatusPMB.PENDING,
        )

        db.add(calon)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            # Antisipasi race condition jika dua request dengan email sama masuk bersamaan
            still_exists = db.scalar(
                select(CalonMahasiswa).where(CalonMahasiswa.email == normalized_email)
            )
            if still_exists is not None:
                raise EmailAlreadyRegisteredError("Email sudah terdaftar") from exc
            raise InvalidReferenceError("Data referensi tidak valid") from exc

        db.refresh(calon)
        return calon
