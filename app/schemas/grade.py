from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class GradeInput(BaseModel):
    nim: str = Field(..., min_length=4, max_length=20, examples=["20240001"])
    kode_mk: str = Field(..., min_length=2, max_length=16, examples=["IF101"])
    semester: str = Field(..., min_length=5, max_length=5, examples=["20251"])
    nilai_huruf: str = Field(..., min_length=1, max_length=2, examples=["A"])
    presensi_persen: Decimal = Field(default=Decimal("100.00"), ge=0, le=100, examples=[90.0])
    actor: str = Field(default="Dr. Daniel Pratama", min_length=1, max_length=64)
    reason: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Wajib diisi jika memperbarui nilai yang sudah ada.",
    )


class GradeUpdateInput(BaseModel):
    nilai_huruf: str = Field(..., min_length=1, max_length=2, examples=["A"])
    presensi_persen: Optional[Decimal] = Field(default=None, ge=0, le=100)
    changed_by: str = Field(..., min_length=1, max_length=64, examples=["Dr. Daniel Pratama"])
    reason: str = Field(..., min_length=1, max_length=500, examples=["Perbaikan nilai setelah remidi UAS"])


class GradeOut(BaseModel):
    id: int
    nim: str
    kode_mk: str
    nama_mk: str
    sks: int
    semester: str
    nilai_huruf: str
    nilai_angka: Decimal
    presensi_persen: Decimal
    updated_by: str
    updated_at: datetime


class GradeMutationResponse(BaseModel):
    """Respons setelah input/edit nilai: langsung menyertakan IPS & IPK terbaru
    sebagai bukti kriteria sukses 'IPK ter-update otomatis saat nilai diinput'.
    """

    grade: GradeOut
    ips: Decimal
    ipk: Decimal
    predikat: str


class GradeHistoryOut(BaseModel):
    id: int
    grade_id: int
    nim: str
    kode_mk: str
    semester: str
    old_value: str
    new_value: str
    changed_by: str
    changed_at: datetime
    reason: str


class TranscriptCourseOut(BaseModel):
    kode_mk: str
    nama_mk: str
    sks: int
    nilai_huruf: str
    nilai_angka: Decimal
    mutu: Decimal
    is_lulus: bool


class TranscriptSemesterOut(BaseModel):
    semester: str
    semester_label: str
    courses: list[TranscriptCourseOut]
    total_sks: int
    total_mutu: Decimal
    ips: Decimal


class TranscriptResponse(BaseModel):
    nim: str
    nama: str
    prodi: str
    angkatan: str
    semesters: list[TranscriptSemesterOut]
    total_sks_lulus: int
    total_mutu_lulus: Decimal
    ipk: Decimal
    predikat: str


class GradeReferenceDataResponse(BaseModel):
    mahasiswa: list[dict[str, str]]
    mata_kuliah: list[dict[str, object]]
