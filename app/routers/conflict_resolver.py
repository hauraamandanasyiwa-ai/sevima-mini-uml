from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.exceptions import ScheduleNotFoundError
from app.models.krs import KRS
from app.models.outbox import OutboxEvent
from app.models.schedule import Jadwal
from app.observers.events import HARI_LABEL
from app.runtime import get_notification_runtime
from app.schemas.schedule import (
    AdminConflictItemOut,
    AdminConflictListResponse,
    ApplySuggestionInput,
    KRSStatusItemOut,
    NotificationAuditResponse,
    NotificationLogOut,
    OutboxEventOut,
    RescheduleSuggestionOut,
    RescheduleSuggestResponse,
    ScheduleOut,
    ScheduleSummaryOut,
)
from app.services.ai_rescheduler import AIReschedulerService
from app.services.scheduling_service import ScheduleData, SchedulingService


def require_admin(
    x_role: str = Header(default="", alias="X-Role"),
) -> str:
    """Dependensi pemeriksa peran: seluruh endpoint Conflict Resolver hanya boleh
    diakses oleh `admin_akademik`.
    """
    if x_role.strip().lower() != "admin_akademik":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Akses ditolak. Endpoint ini khusus untuk peran 'admin_akademik' (header X-Role).",
        )
    return "admin_akademik"


router = APIRouter(
    prefix="/admin",
    tags=["Conflict Resolver (Admin Akademik)"],
    dependencies=[Depends(require_admin)],
)


def get_scheduling_service(db: Session = Depends(get_db)) -> SchedulingService:
    runtime = get_notification_runtime()
    return SchedulingService(session=db, dispatcher=runtime.dispatcher)


def get_ai_rescheduler(db: Session = Depends(get_db)) -> AIReschedulerService:
    return AIReschedulerService(session=db)


def _to_schedule_summary(jadwal: Jadwal) -> ScheduleSummaryOut:
    kode_mk = jadwal.kelas.kode_mk if jadwal.kelas else f"KLS-{jadwal.kelas_id}"
    nama_mk = (
        jadwal.kelas.mata_kuliah.nama
        if jadwal.kelas and jadwal.kelas.mata_kuliah
        else kode_mk
    )
    nama_kelas = jadwal.kelas.nama_kelas if jadwal.kelas else "-"
    dosen_nama = jadwal.dosen.nama if jadwal.dosen else f"Dosen #{jadwal.dosen_id}"
    return ScheduleSummaryOut(
        id=jadwal.id,
        kelas_id=jadwal.kelas_id,
        kode_mk=kode_mk,
        nama_mk=nama_mk,
        nama_kelas=nama_kelas,
        ruangan_kode=jadwal.ruangan_kode,
        dosen_id=jadwal.dosen_id,
        dosen_nama=dosen_nama,
        hari=jadwal.hari,
        hari_nama=HARI_LABEL.get(jadwal.hari, f"Hari-{jadwal.hari}"),
        jam_mulai=jadwal.jam_mulai.strftime("%H:%M"),
        jam_selesai=jadwal.jam_selesai.strftime("%H:%M"),
        sequence=jadwal.sequence,
    )


@router.get("/conflicts", response_model=AdminConflictListResponse)
def list_admin_conflicts(
    db: Session = Depends(get_db),
    service: SchedulingService = Depends(get_scheduling_service),
) -> AdminConflictListResponse:
    """Daftar bentrok lengkap dengan detail mata kuliah, kelas, ruangan, dan dosen
    untuk ditampilkan pada dashboard Conflict Resolver.
    """
    conflicts = service.get_all_conflicts()
    all_jadwals = {j.id: j for j in service.list_jadwals()}

    items: list[AdminConflictItemOut] = []
    for conflict in conflicts:
        involved = [
            _to_schedule_summary(all_jadwals[jid])
            for jid in conflict.affected
            if jid in all_jadwals
        ]
        items.append(
            AdminConflictItemOut(
                type=conflict.type,
                affected=list(conflict.affected),
                schedules=involved,
            )
        )

    return AdminConflictListResponse(total_conflicts=len(items), conflicts=items)


@router.post("/conflicts/{jadwal_id}/suggest", response_model=RescheduleSuggestResponse)
def suggest_reschedule(
    jadwal_id: int,
    rescheduler: AIReschedulerService = Depends(get_ai_rescheduler),
) -> RescheduleSuggestResponse:
    """Meminta sampai 3 saran jadwal pengganti dari AI yang telah melewati 4 saringan
    validasi (JSON parsing, skema Pydantic, ruangan & kapasitas, deteksi bentrok).
    """
    suggestions = rescheduler.suggest_alternatives(jadwal_id=jadwal_id, max_results=3)
    return RescheduleSuggestResponse(
        jadwal_id=jadwal_id,
        suggestions=[
            RescheduleSuggestionOut(
                hari=s.hari,
                hari_nama=HARI_LABEL.get(s.hari, f"Hari-{s.hari}"),
                jam_mulai=s.jam_mulai.strftime("%H:%M"),
                jam_selesai=s.jam_selesai.strftime("%H:%M"),
                ruangan_kode=s.ruangan_kode,
                alasan=s.alasan,
            )
            for s in suggestions
        ],
    )


@router.post("/conflicts/{jadwal_id}/apply", response_model=ScheduleOut)
def apply_reschedule_suggestion(
    jadwal_id: int,
    payload: ApplySuggestionInput,
    db: Session = Depends(get_db),
    service: SchedulingService = Depends(get_scheduling_service),
) -> ScheduleOut:
    """Tombol 'Terapkan' pada Conflict Resolver.

    PRINSIP SATU PINTU: tidak memiliki jalur khusus! Menyusun `ScheduleData`
    dari saran lalu memanggil `SchedulingService.update_jadwal()` yang sama persis
    dengan perubahan manual (cek bentrok ulang -> 409 jika slot sudah terisi,
    invalidasi KRS terdampak ke `revision`, tulis outbox, kirim notif 3 kanal).
    """
    jadwal = db.get(Jadwal, jadwal_id)
    if jadwal is None:
        raise ScheduleNotFoundError(f"Jadwal dengan ID '{jadwal_id}' tidak ditemukan.")

    updated = service.update_jadwal(
        jadwal_id=jadwal_id,
        data=ScheduleData(
            kelas_id=jadwal.kelas_id,
            ruangan_kode=payload.ruangan_kode,
            dosen_id=jadwal.dosen_id,
            hari=payload.hari,
            jam_mulai=payload.jam_mulai,
            jam_selesai=payload.jam_selesai,
        ),
    )
    return ScheduleOut.model_validate(updated)


@router.get("/notifications/logs", response_model=NotificationAuditResponse)
def get_notification_logs(
    db: Session = Depends(get_db),
) -> NotificationAuditResponse:
    """Melihat bukti pengiriman notifikasi 3 kanal (email, sms, push) serta status
    tabel `notification_outbox` untuk verifikasi & demo.
    """
    runtime = get_notification_runtime()
    outbox_rows = list(
        db.scalars(select(OutboxEvent).order_by(OutboxEvent.id.desc()).limit(50)).all()
    )
    logs = [
        NotificationLogOut(
            channel=entry.channel,
            recipient=entry.recipient,
            subject=entry.subject,
            message=entry.message,
            idempotency_key=entry.idempotency_key,
            sent_at=entry.sent_at,
        )
        for entry in reversed(runtime.history[-100:])
    ]
    outbox = [
        OutboxEventOut(
            id=row.id,
            event_id=row.event_id,
            event_type=row.event_type,
            status=row.status,
            attempts=row.attempts,
            last_error=row.last_error,
            created_at=row.created_at,
            sent_at=row.sent_at,
        )
        for row in outbox_rows
    ]
    return NotificationAuditResponse(total_logs=len(logs), logs=logs, outbox=outbox)


@router.get("/krs/status", response_model=list[KRSStatusItemOut])
def list_krs_statuses(
    db: Session = Depends(get_db),
) -> list[KRSStatusItemOut]:
    """Menampilkan status seluruh KRS agar admin dapat memantau KRS yang otomatis
    kembali ke `revision` setelah perubahan jadwal.
    """
    rows = list(db.scalars(select(KRS).order_by(KRS.id)).all())
    return [
        KRSStatusItemOut(
            krs_id=row.id,
            nim=row.nim,
            semester=row.semester,
            status=row.status.value,
            revision_note=row.revision_note,
        )
        for row in rows
    ]
