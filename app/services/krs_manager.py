from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.exceptions import (
    CourseNotFoundError,
    KRSNotFoundError,
    KRSStatusError,
    KRSValidationError,
    MahasiswaNotFoundError,
)
from app.models.krs import (
    EDITABLE_KRS_STATUSES,
    KRS,
    KRSDetail,
    KRSStatus,
    MataKuliah,
)
from app.models.mahasiswa import Mahasiswa
from app.validators import (
    KRSContext,
    SKSValidator,
    ValidationResult,
    Validator,
    build_validation_chain,
    default_validators,
)


class KRSManager:
    """Service layer pintu tunggal untuk mengelola Kartu Rencana Studi (KRS).

    Prinsip desain:
    - Single Responsibility: hanya mengatur alur bisnis & transaksi, tidak
      mengetahui detail HTTP maupun detail tiap aturan validasi.
    - Dependency Injection & Open/Closed: daftar validator disuntikkan lewat
      constructor lalu dirangkai menjadi rantai Chain of Responsibility.
    - Satu transaksi, commit sekali di akhir: validasi dan modifikasi data
      berjalan di dalam transaksi yang sama dengan row lock (`with_for_update`).
    """

    def __init__(
        self,
        session: Session,
        validators: Optional[list[Validator]] = None,
    ) -> None:
        self._session = session
        self._validators: list[Validator] = (
            validators if validators is not None else default_validators()
        )
        self._chain: Optional[Validator] = build_validation_chain(self._validators)

    def _ensure_mahasiswa_exists(self, nim: str) -> Mahasiswa:
        mahasiswa = self._session.get(Mahasiswa, nim)
        if mahasiswa is None:
            raise MahasiswaNotFoundError(nim)
        return mahasiswa

    def _krs_terkunci(self, nim: str, semester: str, *, create_if_missing: bool) -> Optional[KRS]:
        """Mengambil baris KRS milik `nim` pada `semester` dengan row-level lock
        (`SELECT ... FOR UPDATE`) untuk mencegah race condition antar request paralel.

        Jika `create_if_missing=True` dan KRS belum ada, otomatis membuat KRS baru
        berstatus `DRAFT` (menangani potensi race condition pembuatan KRS paralel).
        """
        stmt = (
            select(KRS)
            .where(KRS.nim == nim, KRS.semester == semester)
            .options(selectinload(KRS.details).selectinload(KRSDetail.mata_kuliah))
            .with_for_update()
        )
        krs = self._session.scalars(stmt).first()
        if krs is not None or not create_if_missing:
            return krs

        self._ensure_mahasiswa_exists(nim)

        new_krs = KRS(nim=nim, semester=semester, status=KRSStatus.DRAFT)
        self._session.add(new_krs)
        try:
            self._session.flush()
        except IntegrityError:
            # Dua request bersamaan mencoba membuat KRS yang sama -> rollback & baca ulang terkunci
            self._session.rollback()
            krs = self._session.scalars(stmt).first()
            if krs is not None:
                return krs
            raise

        # Kunci ulang baris KRS yang baru dibuat agar konsisten dalam transaksi aktif
        return self._session.scalars(stmt).one()

    @staticmethod
    def _ensure_editable(krs: KRS) -> None:
        if krs.status not in EDITABLE_KRS_STATUSES:
            raise KRSStatusError(krs.status.value)

    def get_krs(self, nim: str, semester: str) -> KRS:
        """Mengambil KRS mahasiswa pada semester tertentu (read-only)."""
        stmt = (
            select(KRS)
            .where(KRS.nim == nim, KRS.semester == semester)
            .options(selectinload(KRS.details).selectinload(KRSDetail.mata_kuliah))
        )
        krs = self._session.scalars(stmt).first()
        if krs is None:
            raise KRSNotFoundError(
                f"KRS untuk NIM '{nim}' pada semester '{semester}' tidak ditemukan."
            )
        return krs

    def add_course(self, nim: str, semester: str, kode_mk: str) -> KRSDetail:
        """Menambahkan satu mata kuliah ke KRS mahasiswa dalam satu transaksi atomik.

        Alur:
        1. Kunci baris KRS dengan `with_for_update()` (buat DRAFT jika belum ada).
        2. Periksa status KRS (hanya boleh DRAFT atau REVISION).
        3. Ambil data mata kuliah (error jelas jika kode tidak ada).
        4. Jalankan rantai validasi (fail-fast: berhenti pada kegagalan pertama).
        5. Tambahkan baris KRSDetail dan commit sekali di akhir.
        """
        krs = self._krs_terkunci(nim, semester, create_if_missing=True)
        assert krs is not None

        self._ensure_editable(krs)

        course = self._session.get(MataKuliah, kode_mk)
        if course is None:
            raise CourseNotFoundError(kode_mk)

        existing_courses = [detail.mata_kuliah for detail in krs.details]
        context = KRSContext(
            nim=nim,
            semester=semester,
            existing_courses=existing_courses,
            new_course=course,
            session=self._session,
        )

        if self._chain is not None:
            result = self._chain.validate(context)
            if not result.ok:
                raise KRSValidationError(result.message)

        detail = KRSDetail(krs_id=krs.id, kode_mk=course.kode_mk)
        self._session.add(detail)

        try:
            self._session.commit()
        except IntegrityError as exc:
            # Jaring pengaman level database jika terjadi double enrollment paralel
            self._session.rollback()
            raise KRSValidationError(
                f"Mata kuliah {course.nama} ({course.kode_mk}) sudah ada di KRS semester ini."
            ) from exc

        self._session.refresh(detail)
        return detail

    def remove_course(self, nim: str, semester: str, kode_mk: str) -> None:
        """Menghapus satu mata kuliah dari KRS mahasiswa dalam satu transaksi.

        Alur: kunci KRS -> cek status -> cari baris -> hapus -> commit.
        """
        krs = self._krs_terkunci(nim, semester, create_if_missing=False)
        if krs is None:
            raise KRSNotFoundError(
                f"KRS untuk NIM '{nim}' pada semester '{semester}' tidak ditemukan."
            )

        self._ensure_editable(krs)

        target_detail = next(
            (detail for detail in krs.details if detail.kode_mk == kode_mk),
            None,
        )
        if target_detail is None:
            raise KRSNotFoundError(
                f"Mata kuliah '{kode_mk}' tidak ditemukan di KRS NIM '{nim}' semester '{semester}'."
            )

        # Dihapus lewat relasi details (cascade="all, delete-orphan")
        krs.details.remove(target_detail)
        self._session.commit()

    def validate_krs(self, nim: str, semester: str) -> list[ValidationResult]:
        """Memeriksa seluruh aturan pada KRS secara utuh (misal sebelum submit).

        Sesuai keputusan desain (ADR-001):
        - Berbeda dengan `add_course` yang fail-fast, `validate_krs` memanggil
          method `check()` setiap validator secara langsung untuk setiap mata kuliah
          dan mengumpulkan SEMUA kegagalan dalam satu daftar agar mahasiswa dapat
          melihat seluruh masalah dalam satu layar.
        - Mengembalikan list kosong jika KRS 100% valid.
        """
        krs = self.get_krs(nim, semester)
        courses = [detail.mata_kuliah for detail in krs.details]
        if not courses:
            return [
                ValidationResult(
                    ok=False,
                    message="KRS masih kosong. Minimal ambil 1 mata kuliah sebelum diajukan.",
                )
            ]

        failures: list[ValidationResult] = []
        seen_messages: set[str] = set()
        sks_checked = False

        for idx, course in enumerate(courses):
            # Mata kuliah lain di KRS (mengecualikan mata kuliah pada indeks idx sendiri)
            others = [c for j, c in enumerate(courses) if j != idx]
            context = KRSContext(
                nim=nim,
                semester=semester,
                existing_courses=others,
                new_course=course,
                session=self._session,
            )

            for validator in self._validators:
                # SKSValidator bersifat agregat seluruh KRS: cukup cek sekali saja
                if isinstance(validator, SKSValidator):
                    if sks_checked:
                        continue
                    sks_checked = True

                result = validator.check(context)
                if not result.ok and result.message not in seen_messages:
                    seen_messages.add(result.message)
                    failures.append(result)

        return failures

    def submit_krs(self, nim: str, semester: str) -> KRS:
        """Mengajukan KRS (DRAFT/REVISION -> SUBMITTED).

        Implementasi lengkap menggunakan State Machine akan dibangun pada Minggu 6.
        """
        raise NotImplementedError(
            "Method submit_krs akan diimplementasikan pada Minggu 6 bersama State Machine."
        )

    def approve_krs(self, nim: str, semester: str, dosen_pa_id: str) -> KRS:
        """Menyetujui KRS oleh Dosen PA (SUBMITTED -> APPROVED).

        Implementasi lengkap menggunakan State Machine & transaksi persetujuan
        akan dibangun pada Minggu 6.
        """
        raise NotImplementedError(
            "Method approve_krs akan diimplementasikan pada Minggu 6 bersama State Machine."
        )
