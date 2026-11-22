from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.krs import KRS, KRSDetail
from app.models.schedule import Jadwal, Kelas
from app.runtime import get_notification_runtime
from app.schemas.schedule import (
    ConflictItemOut,
    ConflictListResponse,
    ScheduleInput,
    ScheduleOut,
)
from app.services.ical_exporter import export_schedules_to_ics
from app.services.scheduling_service import ScheduleData, SchedulingService

router = APIRouter(prefix="/schedules", tags=["Schedules"])


def get_scheduling_service(db: Session = Depends(get_db)) -> SchedulingService:
    runtime = get_notification_runtime()
    return SchedulingService(session=db, dispatcher=runtime.dispatcher)


@router.get("", response_model=list[ScheduleOut])
def list_schedules(
    service: SchedulingService = Depends(get_scheduling_service),
) -> list[ScheduleOut]:
    """Menampilkan daftar seluruh jadwal kuliah."""
    return [ScheduleOut.model_validate(j) for j in service.list_jadwals()]


@router.get("/conflicts", response_model=ConflictListResponse)
def list_conflicts(
    service: SchedulingService = Depends(get_scheduling_service),
) -> ConflictListResponse:
    """Melaporkan seluruh bentrok ruangan & dosen yang ada di database
    (dibaca oleh dashboard admin dan untuk mendeteksi data lama hasil impor).
    """
    conflicts = service.get_all_conflicts()
    return ConflictListResponse(
        total_conflicts=len(conflicts),
        conflicts=[
            ConflictItemOut(type=c.type, affected=list(c.affected))
            for c in conflicts
        ],
    )


@router.get("/export.ics")
def export_calendar_ics(
    nim: Optional[str] = Query(default=None, description="Filter jadwal berdasarkan NIM mahasiswa"),
    semester: Optional[str] = Query(default=None, description="Filter berdasarkan kode semester, mis. 20251"),
    semester_start: date = Query(default=date(2025, 9, 1), description="Tanggal mulai semester"),
    semester_end: date = Query(default=date(2025, 12, 20), description="Tanggal akhir semester"),
    db: Session = Depends(get_db),
) -> Response:
    """Mengekspor jadwal kuliah ke format iCalendar (.ics) yang kompatibel
    dengan Google Calendar, Apple Calendar, dan kalender ponsel.
    """
    stmt = select(Jadwal).join(Kelas, Jadwal.kelas_id == Kelas.id)
    if nim:
        stmt = (
            stmt.join(KRSDetail, KRSDetail.kelas_id == Kelas.id)
            .join(KRS, KRS.id == KRSDetail.krs_id)
            .where(KRS.nim == nim)
            .distinct()
        )
    if semester:
        stmt = stmt.where(Kelas.semester == semester)
    stmt = stmt.order_by(Jadwal.hari, Jadwal.jam_mulai, Jadwal.id)

    jadwals = list(db.scalars(stmt).all())
    ics_content = export_schedules_to_ics(
        jadwals,
        semester_start=semester_start,
        semester_end=semester_end,
    )
    return Response(
        content=ics_content,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="jadwal-kuliah.ics"'},
    )


@router.post("", response_model=ScheduleOut, status_code=status.HTTP_201_CREATED)
def create_schedule(
    payload: ScheduleInput,
    service: SchedulingService = Depends(get_scheduling_service),
) -> ScheduleOut:
    """Membuat jadwal kuliah baru (menolak bentrok & kapasitas berlebih dengan 409)."""
    jadwal = service.create_jadwal(
        ScheduleData(
            kelas_id=payload.kelas_id,
            ruangan_kode=payload.ruangan_kode,
            dosen_id=payload.dosen_id,
            hari=payload.hari,
            jam_mulai=payload.jam_mulai,
            jam_selesai=payload.jam_selesai,
        )
    )
    return ScheduleOut.model_validate(jadwal)


@router.put("/{jadwal_id}", response_model=ScheduleOut)
def update_schedule(
    jadwal_id: int,
    payload: ScheduleInput,
    service: SchedulingService = Depends(get_scheduling_service),
) -> ScheduleOut:
    """Memperbarui jadwal kuliah, menginvalidasi KRS terdampak ke `revision`,
    menulis Transactional Outbox, lalu mengirim notifikasi 3 kanal setelah commit.
    """
    jadwal = service.update_jadwal(
        jadwal_id=jadwal_id,
        data=ScheduleData(
            kelas_id=payload.kelas_id,
            ruangan_kode=payload.ruangan_kode,
            dosen_id=payload.dosen_id,
            hari=payload.hari,
            jam_mulai=payload.jam_mulai,
            jam_selesai=payload.jam_selesai,
        ),
    )
    return ScheduleOut.model_validate(jadwal)


@router.delete("/{jadwal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schedule(
    jadwal_id: int,
    service: SchedulingService = Depends(get_scheduling_service),
) -> None:
    """Menghapus jadwal kuliah, menginvalidasi KRS terdampak, dan mengirim event
    `schedule_deleted` setelah commit.
    """
    service.delete_jadwal(jadwal_id=jadwal_id)
