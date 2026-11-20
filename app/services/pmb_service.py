from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models.calon_mahasiswa import CalonMahasiswa, StatusPMB
from app.models.jalur_masuk import JalurMasuk
from app.models.program_studi import ProgramStudi
from app.schemas.pmb import (
    JalurStatOut,
    PMBStatsOut,
    ProdiStatOut,
    RegisterRequest,
    StatusOut,
)
from app.services.nim_generator import (
    InvalidNIMDataError,
    NIMCapacityExceededError,
    generate_nim,
)


class EmailAlreadyRegisteredError(Exception):
    """Dilempar ketika email pendaftar sudah terdaftar di sistem."""


class InvalidReferenceError(Exception):
    """Dilempar ketika program studi atau jalur masuk tidak ditemukan."""


class ApplicantNotFoundError(Exception):
    """Dilempar ketika ID pendaftar tidak ditemukan di database."""


class InvalidStatusTransitionError(Exception):
    """Dilempar ketika transisi status melanggar aturan state machine PMB."""


class PMBService:
    """Lapisan aturan bisnis & state machine modul Penerimaan Mahasiswa Baru (PMB)."""

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

        # 3. Buat objek CalonMahasiswa dengan status awal pending
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

    @staticmethod
    def approve(
        db: Session,
        pendaftar_id: int,
        tahun: int | None = None,
        max_retries: int = 3,
    ) -> CalonMahasiswa:
        """Menyetujui pendaftar dan men-generate NIM dalam satu transaksi atomik.

        Aturan State Machine:
        - pending  -> approved (catat approved_at UTC & generate NIM)
        - approved -> approved (idempotent: kembalikan NIM lama tanpa menaikkan counter)
        - rejected -> ditolak (409 Conflict)
        """
        last_error: IntegrityError | None = None

        for _attempt in range(max_retries):
            # Kunci baris pendaftar (SELECT ... FOR UPDATE di MySQL/PostgreSQL)
            calon = db.scalar(
                select(CalonMahasiswa)
                .where(CalonMahasiswa.id == pendaftar_id)
                .with_for_update()
            )
            if calon is None:
                raise ApplicantNotFoundError("Pendaftar tidak ditemukan")

            # Lapis 1 Idempotensi: jika sudah approved dan NIM sudah ada, kembalikan langsung
            if calon.status == StatusPMB.APPROVED and calon.nim is not None:
                return calon

            # Status akhir rejected tidak boleh di-approve
            if calon.status != StatusPMB.PENDING:
                raise InvalidStatusTransitionError(
                    "Pendaftar dengan status rejected tidak dapat di-approve"
                )

            # Validasi data pembentuk NIM (400 Bad Request jika tidak memenuhi syarat)
            prodi = db.get(ProgramStudi, calon.program_studi_id)
            if prodi is None:
                raise InvalidNIMDataError("Program studi pendaftar tidak ditemukan")

            now_utc = datetime.now(timezone.utc)
            target_tahun = tahun if tahun is not None else now_utc.year

            try:
                nim = generate_nim(db=db, tahun=target_tahun, kode_prodi=prodi.kode)
                calon.nim = nim
                calon.status = StatusPMB.APPROVED
                calon.approved_at = now_utc
                db.commit()
            except IntegrityError as exc:
                # Lapis 2 pengaman race condition (unique constraint + retry)
                db.rollback()
                last_error = exc
                continue
            except (InvalidNIMDataError, NIMCapacityExceededError):
                db.rollback()
                raise

            db.refresh(calon)
            return calon

        raise RuntimeError(
            "Gagal memproses persetujuan karena konflik transaksi berulang"
        ) from last_error

    @staticmethod
    def reject(db: Session, pendaftar_id: int) -> CalonMahasiswa:
        """Menolak pendaftar sesuai aturan state machine.

        Aturan State Machine:
        - pending  -> rejected
        - rejected -> rejected (idempotent)
        - approved -> ditolak (409 Conflict)
        """
        calon = db.scalar(
            select(CalonMahasiswa)
            .where(CalonMahasiswa.id == pendaftar_id)
            .with_for_update()
        )
        if calon is None:
            raise ApplicantNotFoundError("Pendaftar tidak ditemukan")

        if calon.status == StatusPMB.REJECTED:
            return calon

        if calon.status != StatusPMB.PENDING:
            raise InvalidStatusTransitionError(
                "Pendaftar yang sudah diterima (approved) tidak dapat ditolak"
            )

        calon.status = StatusPMB.REJECTED
        db.commit()
        db.refresh(calon)
        return calon

    @staticmethod
    def get_status(db: Session, pendaftar_id: int) -> StatusOut:
        """Mengambil status pendaftaran berdasarkan ID tanpa membocorkan data sensitif."""
        calon = db.scalar(
            select(CalonMahasiswa)
            .options(
                joinedload(CalonMahasiswa.program_studi),
                joinedload(CalonMahasiswa.jalur_masuk),
            )
            .where(CalonMahasiswa.id == pendaftar_id)
        )
        if calon is None:
            raise ApplicantNotFoundError("Pendaftar tidak ditemukan")

        return StatusOut(
            id=calon.id,
            nama_lengkap=calon.nama_lengkap,
            program_studi=calon.program_studi.nama,
            jalur_masuk=calon.jalur_masuk.nama,
            status=calon.status,
            nim=calon.nim,
            created_at=calon.created_at,
            approved_at=calon.approved_at,
        )

    @staticmethod
    def get_stats(db: Session) -> PMBStatsOut:
        """Menghitung statistik pendaftar langsung di database menggunakan GROUP BY & OUTER JOIN."""
        total = db.scalar(select(func.count(CalonMahasiswa.id))) or 0

        # 1. Jumlah per status (pastikan semua nilai enum selalu hadir dengan default 0)
        status_rows = db.execute(
            select(CalonMahasiswa.status, func.count(CalonMahasiswa.id)).group_by(
                CalonMahasiswa.status
            )
        ).all()
        per_status = {member.value: 0 for member in StatusPMB}
        for status_val, count in status_rows:
            key = status_val.value if isinstance(status_val, StatusPMB) else str(status_val)
            per_status[key] = int(count)

        # 2. Jumlah per program studi (OUTER JOIN agar prodi dengan 0 pendaftar tetap tampil)
        prodi_rows = db.execute(
            select(
                ProgramStudi.kode,
                ProgramStudi.nama,
                func.count(CalonMahasiswa.id),
            )
            .outerjoin(CalonMahasiswa, CalonMahasiswa.program_studi_id == ProgramStudi.id)
            .group_by(ProgramStudi.id, ProgramStudi.kode, ProgramStudi.nama)
            .order_by(ProgramStudi.kode)
        ).all()
        per_program_studi = [
            ProdiStatOut(kode=kode, nama=nama, jumlah=int(jumlah))
            for kode, nama, jumlah in prodi_rows
        ]

        # 3. Jumlah per jalur masuk (OUTER JOIN agar jalur dengan 0 pendaftar tetap tampil)
        jalur_rows = db.execute(
            select(
                JalurMasuk.nama,
                func.count(CalonMahasiswa.id),
            )
            .outerjoin(CalonMahasiswa, CalonMahasiswa.jalur_masuk_id == JalurMasuk.id)
            .group_by(JalurMasuk.id, JalurMasuk.nama)
            .order_by(JalurMasuk.id)
        ).all()
        per_jalur_masuk = [
            JalurStatOut(nama=nama, jumlah=int(jumlah))
            for nama, jumlah in jalur_rows
        ]

        return PMBStatsOut(
            total_pendaftar=int(total),
            per_status=per_status,
            per_program_studi=per_program_studi,
            per_jalur_masuk=per_jalur_masuk,
        )
