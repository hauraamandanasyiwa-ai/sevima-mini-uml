from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.orm.exc import StaleDataError

from app.exceptions import (
    BillingArrearsError,
    CourseNotFoundError,
    ForbiddenError,
    KRSError,
    KRSLockedError,
    KRSNotFoundError,
    KRSValidationError,
    MahasiswaNotFoundError,
)
from app.models.krs import (
    EDITABLE_KRS_STATUSES,
    KRS,
    KRSAktor,
    KRSApprovalLog,
    KRSDetail,
    KRSStatus,
    MataKuliah,
    Notifikasi,
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


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class KRSManager:
    """Service layer pintu tunggal untuk mengelola Kartu Rencana Studi (KRS).

    Minggu 5 + Minggu 6:
    - Single Responsibility & Dependency Injection (tidak tahu soal HTTP).
    - State Machine terenkapsulasi di `KRS.check_transition()` & `KRS.transition()`.
    - Otorisasi 2 lapis: peran (tabel transisi) + kepemilikan (`dosen_pa_id` / `nim`).
    - Pessimistic locking (`with_for_update()`) di seluruh method pengubah KRS
      ditambah Optimistic locking (`version`) untuk melindungi dari layar basi.
    - Transaction management ACID: semua perubahan di `approve_krs` / `revise_krs`
      (status + timestamp + log audit + notifikasi DB) dibungkus 1 transaksi.
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

    def _krs_terkunci(
        self,
        nim: str,
        semester: str,
        *,
        create_if_missing: bool,
    ) -> Optional[KRS]:
        """Mengambil baris KRS dengan row-level lock (`SELECT ... FOR UPDATE`).

        Semua method yang mengubah KRS (`add_course`, `remove_course`, `submit_krs`,
        `approve_krs`, `revise_krs`) wajib mengambil kunci baris yang sama dan
        memeriksa status SETELAH kunci diperoleh.
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

        mahasiswa = self._ensure_mahasiswa_exists(nim)

        new_krs = KRS(
            nim=nim,
            semester=semester,
            status=KRSStatus.DRAFT,
            dosen_pa_id=mahasiswa.dosen_pa_id,
        )
        self._session.add(new_krs)
        try:
            self._session.flush()
        except IntegrityError:
            self._session.rollback()
            krs = self._session.scalars(stmt).first()
            if krs is not None:
                return krs
            raise

        return self._session.scalars(stmt).one()

    @staticmethod
    def _ensure_editable(krs: KRS) -> None:
        if krs.status not in EDITABLE_KRS_STATUSES:
            raise KRSLockedError(current_status=krs.status.value)

    @staticmethod
    def _ensure_dosen_pa_owner(krs: KRS, dosen_pa_id: str) -> None:
        if not krs.dosen_pa_id or krs.dosen_pa_id != dosen_pa_id:
            raise ForbiddenError(
                f"Dosen PA '{dosen_pa_id}' tidak berwenang memproses KRS mahasiswa "
                f"NIM '{krs.nim}' (Dosen PA terdaftar: '{krs.dosen_pa_id or '-'}')."
            )

    @staticmethod
    def _ensure_version_matches(krs: KRS, expected_version: Optional[int]) -> None:
        if expected_version is not None and krs.version != expected_version:
            raise KRSLockedError(
                f"KRS telah berubah sejak terakhir dibuka (versi Anda: {expected_version}, "
                f"versi terbaru: {krs.version}). Muat ulang KRS sebelum memproses."
            )

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

    def _ensure_no_billing_arrears(self, nim: str) -> None:
        """Business Rule Minggu 11: Mahasiswa dengan tunggakan SPP tidak bisa isi/submit KRS."""
        from app.services.billing_service import has_unpaid_arrears

        if has_unpaid_arrears(self._session, nim):
            raise BillingArrearsError(
                f"Mahasiswa NIM '{nim}' tidak dapat mengisi atau mengajukan KRS "
                "karena masih memiliki tunggakan SPP (status overdue / melewati jatuh tempo)."
            )

    def add_course(self, nim: str, semester: str, kode_mk: str) -> KRSDetail:
        """Menambahkan satu mata kuliah ke KRS dalam satu transaksi atomik."""
        self._ensure_no_billing_arrears(nim)
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
        # Sentuh kolom updated_at pada baris KRS agar `version` ikut naik!
        krs.touch()

        try:
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise KRSValidationError(
                f"Mata kuliah {course.nama} ({course.kode_mk}) sudah ada di KRS semester ini."
            ) from exc
        except StaleDataError as exc:
            self._session.rollback()
            raise KRSLockedError(
                "KRS berubah secara bersamaan oleh permintaan lain. Silakan coba lagi."
            ) from exc

        self._session.refresh(detail)
        return detail

    def remove_course(self, nim: str, semester: str, kode_mk: str) -> None:
        """Menghapus satu mata kuliah dari KRS dalam satu transaksi atomik."""
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

        krs.details.remove(target_detail)
        # Sentuh baris KRS agar `version` ikut naik saat detail dihapus
        krs.touch()
        try:
            self._session.commit()
        except StaleDataError as exc:
            self._session.rollback()
            raise KRSLockedError(
                "KRS berubah secara bersamaan oleh permintaan lain. Silakan coba lagi."
            ) from exc

    def _validate_krs_obj(self, krs: KRS) -> list[ValidationResult]:
        """Helper internal untuk memvalidasi objek KRS yang sudah dimuat/dikunci."""
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
            others = [c for j, c in enumerate(courses) if j != idx]
            context = KRSContext(
                nim=krs.nim,
                semester=krs.semester,
                existing_courses=others,
                new_course=course,
                session=self._session,
            )

            for validator in self._validators:
                if isinstance(validator, SKSValidator):
                    if sks_checked:
                        continue
                    sks_checked = True

                result = validator.check(context)
                if not result.ok and result.message not in seen_messages:
                    seen_messages.add(result.message)
                    failures.append(result)

        return failures

    def validate_krs(self, nim: str, semester: str) -> list[ValidationResult]:
        """Memeriksa seluruh aturan KRS dan mengumpulkan semua error (collect-all)."""
        krs = self.get_krs(nim, semester)
        return self._validate_krs_obj(krs)

    def submit_krs(
        self,
        nim: str,
        semester: str,
        *,
        actor_nim: Optional[str] = None,
    ) -> KRS:
        """Mengajukan KRS mahasiswa (DRAFT/REVISION -> SUBMITTED).

        Urutan ketat:
        1. Otorisasi kepemilikan mahasiswa (jika `actor_nim` disertakan).
        2. Kunci baris KRS dengan `with_for_update()`.
        3. `check_transition()` lebih dulu (fail-fast sebelum validasi mahal).
        4. Tolak KRS kosong.
        5. Validasi ulang seluruh mata kuliah (`_validate_krs_obj`).
        6. Jalankan `krs.transition()`, catat `submitted_at`, tulis log, commit sekali.
        """
        if actor_nim is not None and actor_nim != nim:
            raise ForbiddenError(
                f"Mahasiswa '{actor_nim}' tidak berwenang mengajukan KRS milik NIM '{nim}'."
            )

        self._ensure_no_billing_arrears(nim)

        try:
            krs = self._krs_terkunci(nim, semester, create_if_missing=False)
            if krs is None:
                raise KRSNotFoundError(
                    f"KRS untuk NIM '{nim}' pada semester '{semester}' tidak ditemukan."
                )

            # Cek transisi lebih dulu sebelum validasi mahal
            krs.check_transition(KRSStatus.SUBMITTED, KRSAktor.MAHASISWA)

            # Tolak KRS kosong
            if not krs.details:
                raise KRSError(
                    "KRS kosong tidak dapat diajukan. Tambahkan minimal 1 mata kuliah terlebih dahulu."
                )

            # Validasi menyeluruh ulang (data nilai/jadwal mungkin berubah sejak add_course)
            failures = self._validate_krs_obj(krs)
            if failures:
                gabungan = " | ".join(f.message for f in failures)
                raise KRSValidationError(f"KRS gagal diajukan: {gabungan}")

            krs.transition(KRSStatus.SUBMITTED, KRSAktor.MAHASISWA)
            krs.submitted_at = _utcnow()
            self._session.add(
                KRSApprovalLog(
                    krs_id=krs.id,
                    action="submit",
                    actor_id=nim,
                    note="Mahasiswa mengajukan KRS untuk disetujui Dosen PA.",
                )
            )
            self._session.commit()
        except StaleDataError as exc:
            self._session.rollback()
            raise KRSLockedError(
                "KRS berubah secara bersamaan oleh permintaan lain. Silakan coba lagi."
            ) from exc
        except Exception:
            self._session.rollback()
            raise

        self._session.refresh(krs)
        return krs

    def approve_krs(
        self,
        nim: str,
        semester: str,
        dosen_pa_id: str,
        *,
        expected_version: Optional[int] = None,
    ) -> KRS:
        """Menyetujui KRS oleh Dosen PA (SUBMITTED -> APPROVED) dalam 1 transaksi ACID.

        Empat operasi yang dibungkus menjadi satu unit kerja atomik:
        1. Status berubah menjadi `approved` (via `krs.transition()`).
        2. Waktu persetujuan `approved_at` dicatat.
        3. Baris audit `KRSApprovalLog` ditambahkan.
        4. Catatan `Notifikasi` untuk mahasiswa disimpan di database.
        """
        try:
            krs = self._krs_terkunci(nim, semester, create_if_missing=False)
            if krs is None:
                raise KRSNotFoundError(
                    f"KRS untuk NIM '{nim}' pada semester '{semester}' tidak ditemukan."
                )

            # Lapis 2 otorisasi: hanya Dosen PA mahasiswa ini yang boleh menyetujui
            self._ensure_dosen_pa_owner(krs, dosen_pa_id)
            # Optimistic locking: tolak jika layar dosen basi
            self._ensure_version_matches(krs, expected_version)

            krs.transition(KRSStatus.APPROVED, KRSAktor.DOSEN_PA)
            krs.approved_at = _utcnow()

            self._session.add(
                KRSApprovalLog(
                    krs_id=krs.id,
                    action="approve",
                    actor_id=dosen_pa_id,
                    note="KRS disetujui oleh Dosen PA.",
                )
            )
            self._session.add(
                Notifikasi(
                    nim=krs.nim,
                    krs_id=krs.id,
                    judul=f"KRS Semester {krs.semester} Disetujui",
                    pesan=(
                        f"KRS Anda untuk semester {krs.semester} telah disetujui oleh "
                        f"Dosen PA ({dosen_pa_id})."
                    ),
                )
            )

            self._session.commit()
        except StaleDataError as exc:
            self._session.rollback()
            raise KRSLockedError(
                "KRS telah berubah saat persetujuan diproses. Muat ulang KRS dan coba lagi."
            ) from exc
        except Exception:
            self._session.rollback()
            raise

        self._session.refresh(krs)
        return krs

    def revise_krs(
        self,
        nim: str,
        semester: str,
        dosen_pa_id: str,
        catatan: str,
        *,
        expected_version: Optional[int] = None,
    ) -> KRS:
        """Mengembalikan KRS ke mahasiswa untuk diperbaiki (SUBMITTED -> REVISION).

        Mirip `approve_krs`, dengan syarat tambahan: `catatan` dari Dosen PA wajib diisi.
        """
        if not catatan or not catatan.strip():
            raise KRSError(
                "Catatan revisi dari Dosen PA wajib diisi agar mahasiswa tahu apa yang harus diperbaiki."
            )

        clean_note = catatan.strip()

        try:
            krs = self._krs_terkunci(nim, semester, create_if_missing=False)
            if krs is None:
                raise KRSNotFoundError(
                    f"KRS untuk NIM '{nim}' pada semester '{semester}' tidak ditemukan."
                )

            self._ensure_dosen_pa_owner(krs, dosen_pa_id)
            self._ensure_version_matches(krs, expected_version)

            krs.transition(KRSStatus.REVISION, KRSAktor.DOSEN_PA)
            krs.revision_note = clean_note

            self._session.add(
                KRSApprovalLog(
                    krs_id=krs.id,
                    action="revise",
                    actor_id=dosen_pa_id,
                    note=clean_note,
                )
            )
            self._session.add(
                Notifikasi(
                    nim=krs.nim,
                    krs_id=krs.id,
                    judul=f"KRS Semester {krs.semester} Perlu Revisi",
                    pesan=(
                        f"Dosen PA ({dosen_pa_id}) meminta revisi pada KRS semester "
                        f"{krs.semester}: {clean_note}"
                    ),
                )
            )

            self._session.commit()
        except StaleDataError as exc:
            self._session.rollback()
            raise KRSLockedError(
                "KRS telah berubah saat revisi diproses. Muat ulang KRS dan coba lagi."
            ) from exc
        except Exception:
            self._session.rollback()
            raise

        self._session.refresh(krs)
        return krs
