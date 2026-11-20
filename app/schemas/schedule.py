from datetime import time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ScheduleInput(BaseModel):
    """Schema input untuk Create & Update jadwal.

    Memastikan `jam_mulai` & `jam_selesai` dikonversi ke tipe `datetime.time`
    (bukan string) serta menolak format tidak valid (seperti `jam_selesai <= jam_mulai`)
    dengan HTTP 422 di pintu masuk API sebelum menyentuh service.
    """

    kelas_id: int = Field(..., ge=1, examples=[1])
    ruangan_kode: str = Field(..., min_length=1, max_length=16, examples=["A101"])
    dosen_id: int = Field(..., ge=1, examples=[1])
    hari: int = Field(..., ge=1, le=6, description="1=Senin .. 6=Sabtu", examples=[1])
    jam_mulai: time = Field(..., examples=["08:00:00"])
    jam_selesai: time = Field(..., examples=["09:40:00"])

    @model_validator(mode="after")
    def validate_time_range(self) -> "ScheduleInput":
        if self.jam_selesai <= self.jam_mulai:
            raise ValueError("jam_selesai harus lebih lambat daripada jam_mulai.")
        return self


class ScheduleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kelas_id: int
    ruangan_kode: str
    dosen_id: int
    hari: int
    jam_mulai: time
    jam_selesai: time


class ConflictItemOut(BaseModel):
    type: Literal["room_conflict", "lecturer_conflict"]
    affected: list[int]


class ConflictListResponse(BaseModel):
    total_conflicts: int
    conflicts: list[ConflictItemOut]
