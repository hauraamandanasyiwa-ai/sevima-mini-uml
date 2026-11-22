from datetime import datetime, time
from typing import Literal, Optional

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
    sequence: int = 0


class ConflictItemOut(BaseModel):
    type: Literal["room_conflict", "lecturer_conflict"]
    affected: list[int]


class ConflictListResponse(BaseModel):
    total_conflicts: int
    conflicts: list[ConflictItemOut]


# ============================================================================
# Schema Conflict Resolver, AI Rescheduler, & Monitoring Notifikasi (Minggu 8)
# ============================================================================


class ScheduleSummaryOut(BaseModel):
    id: int
    kelas_id: int
    kode_mk: str
    nama_mk: str
    nama_kelas: str
    ruangan_kode: str
    dosen_id: int
    dosen_nama: str
    hari: int
    hari_nama: str
    jam_mulai: str
    jam_selesai: str
    sequence: int


class AdminConflictItemOut(BaseModel):
    type: Literal["room_conflict", "lecturer_conflict"]
    affected: list[int]
    schedules: list[ScheduleSummaryOut]


class AdminConflictListResponse(BaseModel):
    total_conflicts: int
    conflicts: list[AdminConflictItemOut]


class RescheduleSuggestionOut(BaseModel):
    hari: int
    hari_nama: str
    jam_mulai: str
    jam_selesai: str
    ruangan_kode: str
    alasan: str


class RescheduleSuggestResponse(BaseModel):
    jadwal_id: int
    suggestions: list[RescheduleSuggestionOut]


class ApplySuggestionInput(BaseModel):
    hari: int = Field(..., ge=1, le=6)
    jam_mulai: time
    jam_selesai: time
    ruangan_kode: str = Field(..., min_length=1, max_length=16)

    @model_validator(mode="after")
    def validate_time_range(self) -> "ApplySuggestionInput":
        if self.jam_selesai <= self.jam_mulai:
            raise ValueError("jam_selesai harus lebih lambat daripada jam_mulai.")
        return self


class NotificationLogOut(BaseModel):
    channel: str
    recipient: str
    subject: str
    message: str
    idempotency_key: str
    sent_at: datetime


class OutboxEventOut(BaseModel):
    id: int
    event_id: str
    event_type: str
    status: str
    attempts: int
    last_error: Optional[str] = None
    created_at: datetime
    sent_at: Optional[datetime] = None


class NotificationAuditResponse(BaseModel):
    total_logs: int
    logs: list[NotificationLogOut]
    outbox: list[OutboxEventOut]


class KRSStatusItemOut(BaseModel):
    krs_id: int
    nim: str
    semester: str
    status: str
    revision_note: Optional[str] = None
