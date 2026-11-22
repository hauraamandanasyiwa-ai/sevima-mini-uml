from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exceptions import (
    CourseNotFoundError,
    GradeNotFoundError,
    InsufficientAttendanceError,
    InvalidGradeValueError,
    MahasiswaNotFoundError,
)
from app.models.grade import Grade, GradeHistory
from app.models.krs import KRS, KRSDetail, MataKuliah
from app.models.mahasiswa import Mahasiswa
from app.services.gpa_calculator import konversi_huruf_ke_angka

MIN_ATTENDANCE_PERCENT = Decimal("75.00")


class GradeService:
    """Service layer untuk manajemen nilai & audit trail (Minggu 9-10).

    Menegakkan:
    - Konversi nilai huruf -> angka secara deterministik (`Decimal`).
    - Business Rule presensi minimal 75% (nilai tidak boleh diinput jika < 75%).
    - Audit Trail otomatis ke tabel `grade_history` setiap kali nilai berubah
      dalam satu transaksi atomik.
    - Sinkronisasi ke kolom `krs_detail.nilai` jika baris KRS semester terkait ada.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def _validate_attendance(self, presensi_persen: Decimal) -> Decimal:
        pct = Decimal(str(presensi_persen))
        if pct < Decimal("0") or pct > Decimal("100"):
            raise InvalidGradeValueError("Persentase presensi harus berada di antara 0% sampai 100%.")
        if pct < MIN_ATTENDANCE_PERCENT:
            raise InsufficientAttendanceError(
                f"Nilai tidak dapat diinput karena presensi mahasiswa ({pct:.2f}%) "
                f"kurang dari batas minimal {MIN_ATTENDANCE_PERCENT:.0f}%."
            )
        return pct

    def _parse_grade_letter(self, nilai_huruf: str) -> tuple[str, Decimal]:
        normalized = nilai_huruf.strip().upper()
        try:
            angka = konversi_huruf_ke_angka(normalized)
        except ValueError as exc:
            raise InvalidGradeValueError(str(exc)) from exc
        return normalized, angka

    def _sync_krs_detail(self, nim: str, kode_mk: str, semester: str, nilai_huruf: str) -> None:
        """Menyinkronkan kolom `krs_detail.nilai` (dari Minggu 5) agar modul KRS
        dan prasyarat ikut membaca nilai terbaru secara konsisten.
        """
        detail = self._session.scalars(
            select(KRSDetail)
            .join(KRS, KRS.id == KRSDetail.krs_id)
            .where(
                KRS.nim == nim,
                KRS.semester == semester,
                KRSDetail.kode_mk == kode_mk,
            )
        ).first()
        if detail is not None:
            detail.nilai = nilai_huruf

    def input_grade(
        self,
        *,
        nim: str,
        kode_mk: str,
        semester: str,
        nilai_huruf: str,
        presensi_persen: Decimal,
        actor: str,
        reason: Optional[str] = None,
    ) -> Grade:
        """Menginput nilai baru (atau memperbarui dengan audit trail jika sudah ada)."""
        if self._session.get(Mahasiswa, nim) is None:
            raise MahasiswaNotFoundError(nim)
        if self._session.get(MataKuliah, kode_mk) is None:
            raise CourseNotFoundError(kode_mk)

        pct = self._validate_attendance(presensi_persen)
        huruf, angka = self._parse_grade_letter(nilai_huruf)
        actor_clean = actor.strip() or "dosen"

        existing = self._session.scalars(
            select(Grade).where(
                Grade.nim == nim,
                Grade.kode_mk == kode_mk,
                Grade.semester == semester,
            )
        ).first()

        if existing is not None:
            return self.update_grade(
                grade_id=existing.id,
                new_nilai_huruf=huruf,
                changed_by=actor_clean,
                reason=reason or "",
                presensi_persen=pct,
            )

        try:
            grade = Grade(
                nim=nim,
                kode_mk=kode_mk,
                semester=semester,
                nilai_huruf=huruf,
                nilai_angka=angka,
                presensi_persen=pct,
                updated_by=actor_clean,
            )
            self._session.add(grade)
            self._sync_krs_detail(nim, kode_mk, semester, huruf)
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise

        self._session.refresh(grade)
        return grade

    def update_grade(
        self,
        *,
        grade_id: int,
        new_nilai_huruf: str,
        changed_by: str,
        reason: str,
        presensi_persen: Optional[Decimal] = None,
    ) -> Grade:
        """Mengubah nilai mahasiswa dengan pencatatan audit trail wajib ke `grade_history`."""
        grade = self._session.get(Grade, grade_id)
        if grade is None:
            raise GradeNotFoundError(f"Data nilai dengan ID '{grade_id}' tidak ditemukan.")

        reason_clean = reason.strip()
        if not reason_clean:
            raise InvalidGradeValueError(
                "Alasan perubahan nilai (`reason`) wajib diisi untuk audit trail."
            )

        actor_clean = changed_by.strip()
        if not actor_clean:
            raise InvalidGradeValueError("Identitas pengubah (`changed_by`) wajib diisi.")

        if presensi_persen is not None:
            pct = self._validate_attendance(presensi_persen)
        else:
            pct = self._validate_attendance(Decimal(str(grade.presensi_persen)))

        new_huruf, new_angka = self._parse_grade_letter(new_nilai_huruf)
        old_huruf = grade.nilai_huruf

        try:
            grade.nilai_huruf = new_huruf
            grade.nilai_angka = new_angka
            grade.presensi_persen = pct
            grade.updated_by = actor_clean

            # Catat audit trail ke `grade_history` dalam transaksi yang sama
            self._session.add(
                GradeHistory(
                    grade_id=grade.id,
                    old_value=old_huruf,
                    new_value=new_huruf,
                    changed_by=actor_clean,
                    reason=reason_clean,
                )
            )
            self._sync_krs_detail(grade.nim, grade.kode_mk, grade.semester, new_huruf)
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise

        self._session.refresh(grade)
        return grade

    def list_grades(
        self,
        *,
        nim: Optional[str] = None,
        semester: Optional[str] = None,
    ) -> list[Grade]:
        stmt = select(Grade)
        if nim:
            stmt = stmt.where(Grade.nim == nim)
        if semester:
            stmt = stmt.where(Grade.semester == semester)
        stmt = stmt.order_by(Grade.semester, Grade.nim, Grade.kode_mk)
        return list(self._session.scalars(stmt).all())

    def get_grade_history(self, nim: str) -> list[tuple[GradeHistory, Grade]]:
        """Mengambil seluruh riwayat perubahan nilai milik seorang mahasiswa (terbaru dulu)."""
        if self._session.get(Mahasiswa, nim) is None:
            raise MahasiswaNotFoundError(nim)
        stmt = (
            select(GradeHistory, Grade)
            .join(Grade, Grade.id == GradeHistory.grade_id)
            .where(Grade.nim == nim)
            .order_by(GradeHistory.changed_at.desc(), GradeHistory.id.desc())
        )
        return list(self._session.execute(stmt).all())
