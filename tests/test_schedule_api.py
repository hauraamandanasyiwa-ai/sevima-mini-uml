from datetime import time

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.schedule import Dosen, Jadwal, Kelas


def test_schedule_api_create_conflict_409_and_validation_422(
    api_client: TestClient,
    db_session: Session,
) -> None:
    k_bd_a = db_session.scalars(
        select(Kelas).where(Kelas.kode_mk == "IF202", Kelas.nama_kelas == "A")
    ).one()
    k_bd_b = db_session.scalars(
        select(Kelas).where(Kelas.kode_mk == "IF202", Kelas.nama_kelas == "B")
    ).one()
    d1 = db_session.scalars(select(Dosen).where(Dosen.nidn == "0101018501")).one()
    d2 = db_session.scalars(select(Dosen).where(Dosen.nidn == "0102028602")).one()

    # 1. Format salah (jam_selesai <= jam_mulai) -> 422 dari Pydantic sebelum masuk service
    r_bad = api_client.post(
        "/schedules",
        json={
            "kelas_id": k_bd_a.id,
            "ruangan_kode": "A101",
            "dosen_id": d1.id,
            "hari": 1,
            "jam_mulai": "10:00:00",
            "jam_selesai": "09:00:00",
        },
    )
    assert r_bad.status_code == 422

    # 2. Create jadwal pertama -> 201
    r1 = api_client.post(
        "/schedules",
        json={
            "kelas_id": k_bd_a.id,
            "ruangan_kode": "A101",
            "dosen_id": d1.id,
            "hari": 1,
            "jam_mulai": "08:00:00",
            "jam_selesai": "09:40:00",
        },
    )
    assert r1.status_code == 201
    jadwal_id = r1.json()["id"]

    # 3. Create jadwal kedua di ruang & jam sama -> 409 dengan type room_conflict di body
    r2 = api_client.post(
        "/schedules",
        json={
            "kelas_id": k_bd_b.id,
            "ruangan_kode": "A101",
            "dosen_id": d2.id,
            "hari": 1,
            "jam_mulai": "09:00:00",
            "jam_selesai": "10:40:00",
        },
    )
    assert r2.status_code == 409
    body = r2.json()
    assert any(c["type"] == "room_conflict" for c in body["conflicts"])

    # 4. Update jadwal pertama geser 15 menit -> 200
    r3 = api_client.put(
        f"/schedules/{jadwal_id}",
        json={
            "kelas_id": k_bd_a.id,
            "ruangan_kode": "A101",
            "dosen_id": d1.id,
            "hari": 1,
            "jam_mulai": "08:15:00",
            "jam_selesai": "09:55:00",
        },
    )
    assert r3.status_code == 200
    assert r3.json()["jam_mulai"] == "08:15:00"

    # 5. Sisipkan konflik langsung ke DB (simulasi data lama hasil impor) -> GET /schedules/conflicts
    db_session.add(
        Jadwal(
            kelas_id=k_bd_b.id,
            ruangan_kode="A101",
            dosen_id=d2.id,
            hari=1,
            jam_mulai=time(8, 30),
            jam_selesai=time(10, 0),
        )
    )
    db_session.commit()

    r_conf = api_client.get("/schedules/conflicts")
    assert r_conf.status_code == 200
    assert r_conf.json()["total_conflicts"] >= 1
    assert any(c["type"] == "room_conflict" for c in r_conf.json()["conflicts"])

    # 6. Delete jadwal pertama -> 204
    r_del = api_client.delete(f"/schedules/{jadwal_id}")
    assert r_del.status_code == 204
