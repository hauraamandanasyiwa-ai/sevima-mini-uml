class KRSError(Exception):
    """Base exception untuk seluruh kesalahan bisnis pada modul KRS."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class MahasiswaNotFoundError(KRSError):
    """NIM tidak ditemukan / belum disetujui di modul PMB."""

    def __init__(self, nim: str) -> None:
        super().__init__(
            f"Mahasiswa dengan NIM '{nim}' tidak ditemukan atau belum disetujui di PMB.",
            status_code=404,
        )


class CourseNotFoundError(KRSError):
    """Mata kuliah dengan kode yang diminta tidak ada."""

    def __init__(self, kode_mk: str) -> None:
        super().__init__(
            f"Mata kuliah dengan kode '{kode_mk}' tidak ditemukan.",
            status_code=404,
        )


class KRSNotFoundError(KRSError):
    """KRS atau detail KRS yang dicari tidak ditemukan."""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=404)


class KRSStatusError(KRSError):
    """Operasi tidak diizinkan pada status KRS saat ini."""

    def __init__(self, current_status: str) -> None:
        super().__init__(
            f"KRS berstatus '{current_status}' tidak dapat diubah. "
            "Perubahan hanya diizinkan saat berstatus 'draft' atau 'revision'.",
            status_code=409,
        )


class KRSValidationError(KRSError):
    """Pelanggaran aturan bisnis pada rantai validasi KRS."""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=422)
