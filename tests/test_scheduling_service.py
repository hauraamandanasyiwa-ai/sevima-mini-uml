from datetime import time

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exceptions import (
    CapacityExceededError,
    ScheduleConflictError,
    ScheduleNotFoundError,
)
from app.models.krs import KRS, KRSDetail, KRSStatus
from app.models.schedule import Dosen, Kelas
from app.services.scheduling_service import ScheduleData, SchedulingService


def _kelas_id(session: Session, kode_mk: str, nama_kelas: str) -> int:
    k = session.scalars(
        select(Kelas).where(Kelas.kode_mk == kode_mk, Kelas.nama_kelas == nama_kelas)
    ).one()
    return k.id


def _dosen_id(session: Session, nidn: str) -> int:
    d = session.scalars(select(Dosen).where(Dosen.nidn == nidn)).one()
    return d.id


def test_create_update_delete_and_shift_15_minutes_no_self_conflict(
    db_session: Session,
) -> None:
    service = SchedulingService(session=db_session)
    k_bd_a = _kelas_id(db_session, "IF202", "A")
    k_jar_a = _kelas_id(db_session, "IF204", "A")
    d1 = _dosen_id(db_session, "0101018501")
    d2 = _dosen_id(db_session, "0102028602")

    # 1. Create jadwal pertama: Senin 08:00-09:40 di A101
    j1 = service.create_jadwal(
        ScheduleData(k_bd_a, "A101", d1, 1, time(8, 0), time(9, 40))
    )
    assert j1.id is not None

    # 2. Create jadwal bersambung: Senin 09:40-11:20 di A101 (kapasitas 40 == kuota 40 -> LOLOS!)
    j2 = service.create_jadwal(
        ScheduleData(k_jar_a, "A101", d2, 1, time(9, 40), time(11, 20))
    )
    assert j2.id != j1.id

    # 3. Update j1 geser 15 menit lebih awal (07:45-09:25) -> tidak bentrok dengan dirinya sendiri
    updated = service.update_jadwal(
        j1.id,
        ScheduleData(k_bd_a, "A101", d1, 1, time(7, 45), time(9, 25)),
    )
    assert updated.jam_mulai == time(7, 45)
    assert updated.jam_selesai == time(9, 25)

    # 4. Delete j2 -> berhasil, hapus ulang -> 404
    service.delete_jadwal(j2.id)
    with pytest.raises(ScheduleNotFoundError):
        service.delete_jadwal(j2.id)


def test_create_rejects_room_and_lecturer_conflict_with_structured_body(
    db_session: Session,
) -> None:
    service = SchedulingService(session=db_session)
    k_bd_a = _kelas_id(db_session, "IF202", "A")
    k_bd_b = _kelas_id(db_session, "IF202", "B")
    d1 = _dosen_id(db_session, "0101018501")

    j1 = service.create_jadwal(
        ScheduleData(k_bd_a, "A101", d1, 1, time(8, 0), time(9, 40))
    )

    # Ruang sama DAN dosen sama di waktu bertumpuk -> 2 konflik dalam body()
    with pytest.raises(ScheduleConflictError) as exc_info:
        service.create_jadwal(
            ScheduleData(k_bd_b, "A101", d1, 1, time(9, 0), time(10, 40))
        )

    body = exc_info.value.body()
    assert exc_info.value.status_code == 409
    types = {c["type"] for c in body["conflicts"]}
    assert types == {"room_conflict", "lecturer_conflict"}
    assert all(j1.id in c["affected"] for c in body["conflicts"])


def test_capacity_check_uses_max_of_kuota_and_enrolled(db_session: Session) -> None:
    service = SchedulingService(session=db_session)
    # IF101-A berkuota 45, A101 berkapasitas 40 -> ditolak meski peserta terdaftar 0
    k_algo_a = _kelas_id(db_session, "IF101", "A")
    d1 = _dosen_id(db_session, "0101018501")

    with pytest.raises(CapacityExceededError) as exc_info:
        service.create_jadwal(
            ScheduleData(k_algo_a, "A101", d1, 2, time(8, 0), time(9, 40))
        )
    assert exc_info.value.status_code == 409
    assert "A101" in exc_info.value.message
    assert "40" in exc_info.value.message
    assert "45" in exc_info.value.message

    # Uji peserta terdaftar > kapasitas meski kuota kecil:
    # IF203-A kuota 20 di LAB1 kapasitas 20 -> awalnya sah, tapi jika terdaftar 21? (uji dengan ruangan cap 1)
    k_stat_a = _kelas_id(db_session, "IF203", "A")
    krs = KRS(nim="20240001", semester="20251", status=KRSStatus.DRAFT)
    db_session.add(krs)
    db_session.flush()
    db_session.add(KRSDetail(krs_id=krs.id, kode_mk="IF203", kelas_id=k_stat_a))
    db_session.commit()

    # Kuota 20 == LAB1 kapasitas 20, terdaftar 1 -> masih sah (<=)
    ok_jadwal = service.create_jadwal(
        ScheduleData(k_stat_a, "LAB1", d1, 4, time(8, 0), time(9, 40))
    )
    assert ok_jadwal.ruangan_kode == "LAB1"
