from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.schedule import (
    ConflictItemOut,
    ConflictListResponse,
    ScheduleInput,
    ScheduleOut,
)
from app.services.scheduling_service import ScheduleData, SchedulingService

router = APIRouter(prefix="/schedules", tags=["Schedules"])


def get_scheduling_service(db: Session = Depends(get_db)) -> SchedulingService:
    return SchedulingService(session=db)


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
    """Memperbarui jadwal kuliah (mengecualikan dirinya sendiri dari cek bentrok)."""
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
    """Menghapus jadwal kuliah dalam satu transaksi."""
    service.delete_jadwal(jadwal_id=jadwal_id)
