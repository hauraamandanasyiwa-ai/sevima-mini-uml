from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exceptions import MahasiswaNotFoundError
from app.models.grade import Grade
from app.models.krs import DEFAULT_SKALA_NILAI
from app.models.mahasiswa import Mahasiswa

TWO_PLACES = Decimal("0.01")
ZERO_GPA = Decimal("0.00")

# Huruf nilai yang dinyatakan LULUS (nilai >= D sesuai Step 1 spesifikasi)
PASSING_GRADE_LETTERS: frozenset[str] = frozenset(
    {"A", "A-", "B+", "B", "B-", "C+", "C", "D"}
)


@dataclass(frozen=True)
class GradeRecord:
    """Representasi ringan satu baris nilai untuk perhitungan GPA murni tanpa DB."""

    kode_mk: str
    nama_mk: str
    sks: int
    semester: str
    nilai_huruf: str
    nilai_angka: Decimal


@dataclass(frozen=True)
class TranscriptCourseItem:
    kode_mk: str
    nama_mk: str
    sks: int
    nilai_huruf: str
    nilai_angka: Decimal
    mutu: Decimal
    is_lulus: bool


@dataclass(frozen=True)
class TranscriptSemesterBlock:
    semester: str
    semester_label: str
    courses: list[TranscriptCourseItem]
    total_sks: int
    total_mutu: Decimal
    ips: Decimal


@dataclass(frozen=True)
class TranscriptData:
    nim: str
    nama: str
    prodi: str
    angkatan: str
    semesters: list[TranscriptSemesterBlock]
    total_sks_lulus: int
    total_mutu_lulus: Decimal
    ipk: Decimal
    predikat: str


def _round_gpa(value: Decimal) -> Decimal:
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def is_lulus_mk(nilai_huruf: str) -> bool:
    """Business Rule: Lulus MK jika nilai >= D (E dinyatakan tidak lulus)."""
    return nilai_huruf.strip().upper() in PASSING_GRADE_LETTERS


def konversi_huruf_ke_angka(nilai_huruf: str) -> Decimal:
    """Konversi nilai huruf ke bobot angka menggunakan skala standar (A=4.00 .. E=0.00)."""
    key = nilai_huruf.strip().upper()
    if key not in DEFAULT_SKALA_NILAI:
        raise ValueError(
            f"Nilai huruf '{nilai_huruf}' tidak valid. "
            f"Pilihan sah: {', '.join(DEFAULT_SKALA_NILAI.keys())}."
        )
    return DEFAULT_SKALA_NILAI[key]


def tentukan_predikat(ipk: Decimal, total_sks_lulus: int) -> str:
    """Business Rule Predikat Kelulusan berdasarkan IPK kumulatif:
    - IPK >= 3.50          : Cum Laude
    - 3.00 <= IPK <= 3.49  : Sangat Memuaskan
    - 2.75 <= IPK < 3.00   : Memuaskan
    - 2.00 <= IPK < 2.75   : Cukup
    - IPK < 2.00           : Kurang (atau Belum Ada Nilai jika SKS = 0)
    """
    if total_sks_lulus <= 0:
        return "Belum Ada Nilai"
    if ipk >= Decimal("3.50"):
        return "Cum Laude"
    if ipk >= Decimal("3.00"):
        return "Sangat Memuaskan"
    if ipk >= Decimal("2.75"):
        return "Memuaskan"
    if ipk >= Decimal("2.00"):
        return "Cukup"
    return "Kurang"


def format_semester_label(semester: str) -> str:
    """Mengubah kode '20251' -> '2025/2026 Ganjil', '20252' -> '2025/2026 Genap'."""
    if len(semester) == 5 and semester.isdigit():
        tahun = int(semester[:4])
        periode = "Ganjil" if semester[4] == "1" else "Genap" if semester[4] == "2" else "Pendek"
        return f"Semester {periode} {tahun}/{tahun + 1} ({semester})"
    return f"Semester {semester}"


def _derive_angkatan(nim: str) -> str:
    return nim[:4] if len(nim) >= 4 and nim[:4].isdigit() else "-"


def calculate_ips_from_records(records: Sequence[GradeRecord]) -> Decimal:
    """Menghitung IPS untuk sekumpulan mata kuliah dalam satu semester:
    IPS = sum(SKS * Nilai Angka) / sum(SKS).
    Jika belum ada nilai pada semester tersebut -> return 0.00.
    """
    total_sks = sum(r.sks for r in records)
    if total_sks <= 0:
        return ZERO_GPA
    total_mutu = sum((Decimal(r.sks) * r.nilai_angka for r in records), Decimal("0.00"))
    return _round_gpa(total_mutu / Decimal(total_sks))


def calculate_ipk_from_records(records: Sequence[GradeRecord]) -> tuple[Decimal, int, Decimal]:
    """Menghitung IPK kumulatif sesuai aturan Step 1:
    - IPK = sum(SKS * Nilai Angka) / sum(SKS)
    - Hanya hitung MK yang sudah lulus (nilai >= D).
    - Jika MK diulang di beberapa semester, ambil nilai tertinggi.
    - Edge case: belum ada nilai lulus -> return (0.00, 0, 0.00).

    Mengembalikan tuple `(ipk, total_sks_lulus, total_mutu_lulus)`.
    """
    best_by_mk: dict[str, GradeRecord] = {}
    for rec in records:
        if not is_lulus_mk(rec.nilai_huruf):
            continue
        prev = best_by_mk.get(rec.kode_mk)
        if prev is None or rec.nilai_angka > prev.nilai_angka:
            best_by_mk[rec.kode_mk] = rec

    if not best_by_mk:
        return ZERO_GPA, 0, Decimal("0.00")

    total_sks = sum(r.sks for r in best_by_mk.values())
    if total_sks <= 0:
        return ZERO_GPA, 0, Decimal("0.00")

    total_mutu = sum(
        (Decimal(r.sks) * r.nilai_angka for r in best_by_mk.values()),
        Decimal("0.00"),
    )
    return _round_gpa(total_mutu / Decimal(total_sks)), total_sks, _round_gpa(total_mutu)


def _fetch_grade_records(
    session: Session,
    nim: str,
    *,
    semester: str | None = None,
) -> list[GradeRecord]:
    stmt = select(Grade).where(Grade.nim == nim)
    if semester is not None:
        stmt = stmt.where(Grade.semester == semester)
    stmt = stmt.order_by(Grade.semester, Grade.kode_mk)
    rows = list(session.scalars(stmt).all())
    return [
        GradeRecord(
            kode_mk=row.kode_mk,
            nama_mk=row.mata_kuliah.nama if row.mata_kuliah else row.kode_mk,
            sks=row.mata_kuliah.sks if row.mata_kuliah else 0,
            semester=row.semester,
            nilai_huruf=row.nilai_huruf,
            nilai_angka=Decimal(str(row.nilai_angka)),
        )
        for row in rows
    ]


def calculate_ips(session: Session, nim: str, semester: str) -> Decimal:
    """Menghitung IP Semester (IPS) untuk mahasiswa `nim` pada `semester`."""
    if session.get(Mahasiswa, nim) is None:
        raise MahasiswaNotFoundError(nim)
    records = _fetch_grade_records(session, nim, semester=semester)
    return calculate_ips_from_records(records)


def calculate_ipk(session: Session, nim: str) -> Decimal:
    """Menghitung IP Kumulatif (IPK) untuk mahasiswa `nim`.

    Aturan:
    - Hanya menghitung MK lulus (nilai >= D).
    - Jika MK diulang, mengambil nilai tertinggi.
    - Belum ada nilai -> mengembalikan Decimal('0.00').
    """
    if session.get(Mahasiswa, nim) is None:
        raise MahasiswaNotFoundError(nim)
    records = _fetch_grade_records(session, nim)
    ipk, _, _ = calculate_ipk_from_records(records)
    return ipk


def get_transcript(session: Session, nim: str) -> TranscriptData:
    """Menyusun full academic record (transkrip lengkap) seorang mahasiswa."""
    mahasiswa = session.get(Mahasiswa, nim)
    if mahasiswa is None:
        raise MahasiswaNotFoundError(nim)

    records = _fetch_grade_records(session, nim)
    grouped: dict[str, list[GradeRecord]] = defaultdict(list)
    for rec in records:
        grouped[rec.semester].append(rec)

    semester_blocks: list[TranscriptSemesterBlock] = []
    for sem_code in sorted(grouped.keys()):
        sem_records = grouped[sem_code]
        items: list[TranscriptCourseItem] = []
        sem_sks = 0
        sem_mutu = Decimal("0.00")
        for rec in sem_records:
            mutu = _round_gpa(Decimal(rec.sks) * rec.nilai_angka)
            sem_sks += rec.sks
            sem_mutu += mutu
            items.append(
                TranscriptCourseItem(
                    kode_mk=rec.kode_mk,
                    nama_mk=rec.nama_mk,
                    sks=rec.sks,
                    nilai_huruf=rec.nilai_huruf,
                    nilai_angka=rec.nilai_angka,
                    mutu=mutu,
                    is_lulus=is_lulus_mk(rec.nilai_huruf),
                )
            )
        ips = calculate_ips_from_records(sem_records)
        semester_blocks.append(
            TranscriptSemesterBlock(
                semester=sem_code,
                semester_label=format_semester_label(sem_code),
                courses=items,
                total_sks=sem_sks,
                total_mutu=_round_gpa(sem_mutu),
                ips=ips,
            )
        )

    ipk, total_sks_lulus, total_mutu_lulus = calculate_ipk_from_records(records)
    predikat = tentukan_predikat(ipk, total_sks_lulus)

    return TranscriptData(
        nim=mahasiswa.nim,
        nama=mahasiswa.nama,
        prodi=mahasiswa.prodi,
        angkatan=_derive_angkatan(mahasiswa.nim),
        semesters=semester_blocks,
        total_sks_lulus=total_sks_lulus,
        total_mutu_lulus=total_mutu_lulus,
        ipk=ipk,
        predikat=predikat,
    )
