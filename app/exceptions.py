from typing import Any


class KRSError(Exception):
    """Base exception untuk seluruh kesalahan bisnis pada modul KRS."""

    status_code: int = 400

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code

    def body(self) -> dict[str, Any]:
        return {"detail": self.message}


class ForbiddenError(KRSError):
    """403 Forbidden: aktor tidak memiliki hak kepemilikan/otorisasi atas KRS ini."""

    status_code: int = 403


class TransitionError(KRSError):
    """409 Conflict: aktor valid tetapi perpindahan status tidak diizinkan."""

    status_code: int = 409


class KRSLockedError(KRSError):
    """409 Conflict: KRS terkunci (bukan draft/revision) atau konflik versi (stale screen)."""

    status_code: int = 409

    def __init__(self, message: str | None = None, current_status: str | None = None) -> None:
        if message is None:
            if current_status is not None:
                message = (
                    f"KRS berstatus '{current_status}' terkunci dan tidak dapat diubah. "
                    "Perubahan hanya diizinkan saat berstatus 'draft' atau 'revision'."
                )
            else:
                message = "KRS sedang terkunci atau telah berubah oleh proses lain."
        super().__init__(message, status_code=self.status_code)


# Alias kompatibilitas dengan Minggu 5
KRSStatusError = KRSLockedError


class MahasiswaNotFoundError(KRSError):
    """404 Not Found: NIM tidak ditemukan / belum disetujui di modul PMB."""

    status_code: int = 404

    def __init__(self, nim: str) -> None:
        super().__init__(
            f"Mahasiswa dengan NIM '{nim}' tidak ditemukan atau belum disetujui di PMB.",
            status_code=self.status_code,
        )


class CourseNotFoundError(KRSError):
    """404 Not Found: Mata kuliah dengan kode yang diminta tidak ada."""

    status_code: int = 404

    def __init__(self, kode_mk: str) -> None:
        super().__init__(
            f"Mata kuliah dengan kode '{kode_mk}' tidak ditemukan.",
            status_code=self.status_code,
        )


class KRSNotFoundError(KRSError):
    """404 Not Found: KRS atau detail KRS yang dicari tidak ditemukan."""

    status_code: int = 404


class KRSValidationError(KRSError):
    """400 Bad Request: Pelanggaran aturan bisnis pada rantai validasi KRS."""

    status_code: int = 400


# ============================================================================
# Hierarki Exception Polimorfik untuk Modul Jadwal & Ruang (Minggu 7)
# ============================================================================


class ScheduleError(Exception):
    """Kelas dasar error modul jadwal dengan `status_code` dan method polimorfik `body()`."""

    status_code: int = 400

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code

    def body(self) -> dict[str, Any]:
        return {"detail": self.message}


class ScheduleNotFoundError(ScheduleError):
    """404 Not Found: Jadwal, kelas, ruangan, atau dosen tidak ditemukan."""

    status_code: int = 404


class CapacityExceededError(ScheduleError):
    """409 Conflict: Kebutuhan kursi kelas melebihi kapasitas ruangan."""

    status_code: int = 409


class ScheduleConflictError(ScheduleError):
    """409 Conflict: Jadwal bentrok pada dimensi ruangan dan/atau dosen.

    Menimpa `body()` secara polimorfik untuk menyertakan daftar konflik
    terstruktur (`type` dan `affected`) agar frontend/dashboard admin langsung
    tahu jadwal mana yang berbenturan.
    """

    status_code: int = 409

    def __init__(self, message: str, conflicts: list[dict[str, Any]]) -> None:
        super().__init__(message, status_code=self.status_code)
        self.conflicts = conflicts

    def body(self) -> dict[str, Any]:
        return {
            "detail": self.message,
            "conflicts": self.conflicts,
        }


# ============================================================================
# Hierarki Exception Polimorfik untuk Modul Nilai & Transkrip (Minggu 9-10)
# ============================================================================


class GradeError(Exception):
    """Kelas dasar error modul nilai & transkrip."""

    status_code: int = 400

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code

    def body(self) -> dict[str, Any]:
        return {"detail": self.message}


class GradeNotFoundError(GradeError):
    """404 Not Found: data nilai, mahasiswa, atau mata kuliah tidak ditemukan."""

    status_code: int = 404


class InsufficientAttendanceError(GradeError):
    """400 Bad Request: presensi mahasiswa < 75% sehingga nilai tidak boleh diinput."""

    status_code: int = 400


class InvalidGradeValueError(GradeError):
    """400 Bad Request: nilai huruf tidak valid atau alasan perubahan nilai kosong."""

    status_code: int = 400
