class KRSError(Exception):
    """Base exception untuk seluruh kesalahan bisnis pada modul KRS.

    Memiliki atribut `status_code` sehingga cukup satu exception handler
    di FastAPI untuk menangani semua turunannya secara polimorfik.
    """

    status_code: int = 400

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code


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
