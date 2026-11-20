from datetime import datetime, time
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class AddCourseRequest(BaseModel):
    kode_mk: str = Field(..., min_length=2, max_length=16, examples=["IF202"])


class SubmitKRSRequest(BaseModel):
    # Opsional: idealnya diambil dari token login; sementara bisa dikirim untuk uji otorisasi
    actor_nim: Optional[str] = Field(default=None, examples=["20240001"])


class ApproveKRSRequest(BaseModel):
    # Catatan limitasi: idealnya diambil dari identitas login (JWT) agar tidak bisa dipalsukan
    dosen_pa_id: str = Field(..., min_length=2, max_length=32, examples=["PA001"])
    version: Optional[int] = Field(
        default=None,
        ge=1,
        description="Versi KRS yang dilihat dosen di layar (Optimistic Locking).",
        examples=[2],
    )


class ReviseKRSRequest(BaseModel):
    dosen_pa_id: str = Field(..., min_length=2, max_length=32, examples=["PA001"])
    catatan: str = Field(
        ...,
        min_length=1,
        max_length=500,
        examples=["Silakan ambil mata kuliah wajib Basis Data terlebih dahulu."],
    )
    version: Optional[int] = Field(default=None, ge=1, examples=[2])


class RecommendKRSRequest(BaseModel):
    desired_kode_mk: list[str] = Field(..., min_length=1, examples=[["IF202", "IF203", "IF204", "MA201"]])
    target_sks: int = Field(default=24, ge=1, le=24)


class MataKuliahOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    kode_mk: str
    nama: str
    sks: int
    hari: int
    jam_mulai: time
    jam_selesai: time
    is_wajib: bool = True


class KRSDetailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kode_mk: str
    nilai: Optional[str] = None
    mata_kuliah: MataKuliahOut


class KRSOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nim: str
    semester: str
    status: str
    dosen_pa_id: Optional[str] = None
    submitted_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    revision_note: Optional[str] = None
    version: int
    total_sks: int
    details: list[KRSDetailOut]


class ValidationIssueOut(BaseModel):
    ok: bool
    message: str


class ValidateKRSResponse(BaseModel):
    valid: bool
    errors: list[ValidationIssueOut]


class RecommendKRSResponse(BaseModel):
    total_sks: int
    selected_courses: list[MataKuliahOut]
    skipped_reasons: dict[str, str]
