from datetime import time
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class AddCourseRequest(BaseModel):
    kode_mk: str = Field(..., min_length=2, max_length=16, examples=["IF201"])


class MataKuliahOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    kode_mk: str
    nama: str
    sks: int
    hari: int
    jam_mulai: time
    jam_selesai: time


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
    total_sks: int
    details: list[KRSDetailOut]


class ValidationIssueOut(BaseModel):
    ok: bool
    message: str


class ValidateKRSResponse(BaseModel):
    valid: bool
    errors: list[ValidationIssueOut]
