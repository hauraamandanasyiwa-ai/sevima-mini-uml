from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.nim_counter import NimCounter

MAX_NIM_SEQUENCE = 9999


class InvalidNIMDataError(ValueError):
    """Dilempar ketika data pembentuk NIM (tahun/kode prodi/nomor urut) tidak valid."""


class NIMCapacityExceededError(OverflowError):
    """Dilempar ketika nomor urut NIM melampaui batas 4 digit (9999)."""


def format_nim(tahun: int, kode_prodi: str, nomor_urut: int) -> str:
    """Pure function untuk membentuk NIM 11 digit: YYYY + PPP + NNNN.

    Keputusan desain (lihat docs/ADR-002-pmb-approve-nim-testing.md):
    menggunakan 11 digit angka murni tanpa tanda strip agar mudah disimpan,
    diurutkan, dan divalidasi secara konsisten.
    """
    if not (1000 <= tahun <= 9999):
        raise InvalidNIMDataError("Tahun NIM harus terdiri dari 4 digit (1000-9999)")

    cleaned_kode = kode_prodi.strip()
    if len(cleaned_kode) != 3 or not cleaned_kode.isdigit():
        raise InvalidNIMDataError("Kode program studi harus berupa 3 digit angka")

    if not (1 <= nomor_urut <= MAX_NIM_SEQUENCE):
        raise InvalidNIMDataError(
            f"Nomor urut NIM harus berada di rentang 1 sampai {MAX_NIM_SEQUENCE}"
        )

    return f"{tahun:04d}{cleaned_kode}{nomor_urut:04d}"


def generate_nim(db: Session, tahun: int, kode_prodi: str) -> str:
    """Menghasilkan NIM baru secara aman terhadap race condition memakai tabel nim_counter.

    Catatan arsitektur:
    - Menggunakan SELECT ... FOR UPDATE (with_for_update) agar di MySQL/InnoDB atau
      PostgreSQL baris counter terkunci hingga transaksi caller selesai.
    - Sengaja hanya memanggil db.flush(), BUKAN db.commit(), karena pengelolaan
      transaksi menjadi tanggung jawab PMBService.approve().
    """
    cleaned_kode = kode_prodi.strip()
    if len(cleaned_kode) != 3 or not cleaned_kode.isdigit():
        raise InvalidNIMDataError("Kode program studi harus berupa 3 digit angka")

    if not (1000 <= tahun <= 9999):
        raise InvalidNIMDataError("Tahun NIM harus terdiri dari 4 digit (1000-9999)")

    stmt = (
        select(NimCounter)
        .where(NimCounter.tahun == tahun, NimCounter.kode_prodi == cleaned_kode)
        .with_for_update()
    )
    counter = db.scalar(stmt)

    if counter is None:
        # Inisialisasi eksplisit last_number=0 karena default kolom hanya berlaku saat INSERT
        counter = NimCounter(tahun=tahun, kode_prodi=cleaned_kode, last_number=0)
        db.add(counter)

    if counter.last_number >= MAX_NIM_SEQUENCE:
        raise NIMCapacityExceededError(
            f"Kapasitas nomor urut NIM untuk prodi {cleaned_kode} tahun {tahun} telah penuh"
        )

    counter.last_number += 1
    db.flush()

    return format_nim(tahun=tahun, kode_prodi=cleaned_kode, nomor_urut=counter.last_number)
