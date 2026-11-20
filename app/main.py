from contextlib import asynccontextmanager
from datetime import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import Base, SessionLocal, engine
from app.exceptions import KRSError, ScheduleError
from app.models.krs import (
    DEFAULT_SKALA_NILAI,
    KRS,
    KRSDetail,
    KRSStatus,
    MataKuliah,
    SkalaNilai,
)
from app.models.mahasiswa import Mahasiswa
from app.models.schedule import Dosen, Jadwal, Kelas, Ruangan
from app.routers.krs import router as krs_router
from app.routers.schedule import router as schedule_router


def seed_skala_nilai(session: Session) -> None:
    """Mengisi tabel skala_nilai jika belum ada agar query prasyarat siap pakai."""
    for huruf, bobot in DEFAULT_SKALA_NILAI.items():
        if session.get(SkalaNilai, huruf) is None:
            session.add(SkalaNilai(huruf=huruf, bobot=bobot))
    session.commit()


def seed_dummy_data(session: Session) -> None:
    """Mengisi data dummy KRS (Minggu 5 & 6) secara idempoten."""
    if session.get(Mahasiswa, "20240001") is None:
        session.add(
            Mahasiswa(
                nim="20240001",
                nama="Budi Santoso",
                prodi="Teknik Informatika",
                dosen_pa_id="PA001",
            )
        )
    if session.get(Mahasiswa, "20240002") is None:
        session.add(
            Mahasiswa(
                nim="20240002",
                nama="Siti Rahma",
                prodi="Teknik Informatika",
                dosen_pa_id="PA002",
            )
        )

    courses_spec = [
        ("IF101", "Algoritma dan Pemrograman", 3, 1, time(8, 0), time(10, 30), True),
        ("MA101", "Kalkulus 1", 3, 2, time(8, 0), time(10, 30), True),
        ("IF201", "Struktur Data", 3, 3, time(8, 0), time(10, 30), True),
        ("MA201", "Kalkulus 2", 3, 4, time(8, 0), time(10, 30), True),
        ("IF202", "Basis Data", 3, 1, time(8, 0), time(10, 30), True),
        ("IF203", "Statistika", 3, 1, time(9, 0), time(11, 0), False),
        ("IF204", "Jaringan Komputer", 3, 1, time(10, 30), time(13, 0), True),
    ]
    for kode, nama, sks, hari, mulai, selesai, is_wajib in courses_spec:
        if session.get(MataKuliah, kode) is None:
            session.add(
                MataKuliah(
                    kode_mk=kode,
                    nama=nama,
                    sks=sks,
                    hari=hari,
                    jam_mulai=mulai,
                    jam_selesai=selesai,
                    is_wajib=is_wajib,
                )
            )
    session.flush()

    algoritma = session.get(MataKuliah, "IF101")
    kalkulus1 = session.get(MataKuliah, "MA101")
    struktur_data = session.get(MataKuliah, "IF201")
    kalkulus2 = session.get(MataKuliah, "MA201")

    if struktur_data and algoritma and algoritma not in struktur_data.prasyarat:
        struktur_data.prasyarat.append(algoritma)
    if kalkulus2 and kalkulus1 and kalkulus1 not in kalkulus2.prasyarat:
        kalkulus2.prasyarat.append(kalkulus1)

    budi_prev = session.scalars(
        select(KRS).where(KRS.nim == "20240001", KRS.semester == "20242")
    ).first()
    if budi_prev is None:
        budi_prev = KRS(
            nim="20240001",
            semester="20242",
            status=KRSStatus.APPROVED,
            dosen_pa_id="PA001",
        )
        session.add(budi_prev)
        session.flush()
        session.add_all(
            [
                KRSDetail(krs_id=budi_prev.id, kode_mk="MA101", nilai="B"),
                KRSDetail(krs_id=budi_prev.id, kode_mk="IF101", nilai="D"),
            ]
        )

    siti_prev = session.scalars(
        select(KRS).where(KRS.nim == "20240002", KRS.semester == "20242")
    ).first()
    if siti_prev is None:
        siti_prev = KRS(
            nim="20240002",
            semester="20242",
            status=KRSStatus.APPROVED,
            dosen_pa_id="PA002",
        )
        session.add(siti_prev)
        session.flush()
        session.add(KRSDetail(krs_id=siti_prev.id, kode_mk="IF101", nilai="C"))

    session.commit()


def seed_schedule_dummy_data(session: Session) -> None:
    """Mengisi data dummy Ruang, Dosen, Kelas, dan Jadwal (Minggu 7) secara idempoten.

    Sengaja menyertakan 2 konflik awal (seperti data lama hasil impor sebelum
    SchedulingService aktif) agar `GET /schedules/conflicts` langsung memperlihatkan
    `room_conflict` dan `lecturer_conflict` di Swagger UI.
    """
    ruang_spec = [
        ("A101", "Ruang Kuliah A101", 40),
        ("B201", "Ruang Kuliah B201", 30),
        ("LAB1", "Laboratorium Komputer 1", 25),
    ]
    for kode, nama, kapasitas in ruang_spec:
        if session.get(Ruangan, kode) is None:
            session.add(Ruangan(kode=kode, nama=nama, kapasitas=kapasitas))

    dosen_spec = [
        ("0101018501", "Dr. Daniel Pratama"),
        ("0102028602", "Prof. Rina Kusuma"),
        ("0103038703", "Ir. Hendra Wijaya"),
    ]
    dosen_map: dict[str, Dosen] = {}
    for nidn, nama in dosen_spec:
        existing = session.scalars(select(Dosen).where(Dosen.nidn == nidn)).first()
        if existing is None:
            existing = Dosen(nidn=nidn, nama=nama)
            session.add(existing)
            session.flush()
        dosen_map[nidn] = existing

    kelas_spec = [
        ("IF202", "A", 35, "20251"),
        ("IF202", "B", 30, "20251"),
        ("IF203", "A", 25, "20251"),
        ("IF204", "A", 40, "20251"),
        ("IF101", "A", 35, "20251"),
    ]
    kelas_map: dict[tuple[str, str], Kelas] = {}
    for kode_mk, nama_kelas, kuota, sem in kelas_spec:
        existing = session.scalars(
            select(Kelas).where(
                Kelas.kode_mk == kode_mk,
                Kelas.nama_kelas == nama_kelas,
                Kelas.semester == sem,
            )
        ).first()
        if existing is None:
            existing = Kelas(
                kode_mk=kode_mk,
                nama_kelas=nama_kelas,
                kuota=kuota,
                semester=sem,
            )
            session.add(existing)
            session.flush()
        kelas_map[(kode_mk, nama_kelas)] = existing

    # Seed jadwal hanya jika tabel jadwal masih kosong
    has_jadwal = session.scalars(select(Jadwal).limit(1)).first()
    if has_jadwal is None:
        d1 = dosen_map["0101018501"].id
        d2 = dosen_map["0102028602"].id
        d3 = dosen_map["0103038703"].id

        session.add_all(
            [
                # Jadwal #1: Basis Data A, Senin 08:00-09:40, A101, Dosen 1
                Jadwal(
                    kelas_id=kelas_map[("IF202", "A")].id,
                    ruangan_kode="A101",
                    dosen_id=d1,
                    hari=1,
                    jam_mulai=time(8, 0),
                    jam_selesai=time(9, 40),
                ),
                # Jadwal #2 (BERSAMBUNG, AMAN): Jaringan A, Senin 09:40-11:20, A101, Dosen 2
                Jadwal(
                    kelas_id=kelas_map[("IF204", "A")].id,
                    ruangan_kode="A101",
                    dosen_id=d2,
                    hari=1,
                    jam_mulai=time(9, 40),
                    jam_selesai=time(11, 20),
                ),
                # Jadwal #3 (SENGAJA ROOM CONFLICT dengan #1): Statistika A, Senin 08:30-10:00, A101, Dosen 3
                Jadwal(
                    kelas_id=kelas_map[("IF203", "A")].id,
                    ruangan_kode="A101",
                    dosen_id=d3,
                    hari=1,
                    jam_mulai=time(8, 30),
                    jam_selesai=time(10, 0),
                ),
                # Jadwal #4 (SENGAJA LECTURER CONFLICT dengan #1): Basis Data B, Senin 08:30-10:10, B201, Dosen 1
                Jadwal(
                    kelas_id=kelas_map[("IF202", "B")].id,
                    ruangan_kode="B201",
                    dosen_id=d1,
                    hari=1,
                    jam_mulai=time(8, 30),
                    jam_selesai=time(10, 10),
                ),
                # Jadwal #5 (AMAN, beda hari): Algoritma A, Rabu 08:00-09:40, A101, Dosen 1
                Jadwal(
                    kelas_id=kelas_map[("IF101", "A")].id,
                    ruangan_kode="A101",
                    dosen_id=d1,
                    hari=3,
                    jam_mulai=time(8, 0),
                    jam_selesai=time(9, 40),
                ),
            ]
        )

    session.commit()


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        seed_skala_nilai(session)
        seed_dummy_data(session)
        seed_schedule_dummy_data(session)
    yield


app = FastAPI(
    title="SIMAK Mini — Modul Jadwal & Ruang (Minggu 7)",
    description=(
        "SEVIMA Mini terintegrasi (Modul KRS Minggu 5-6 + Modul Jadwal & Ruang Minggu 7): "
        "Model Ruangan/Dosen/Kelas/Jadwal, Detektor Bentrok 3 Dimensi (Naive + Sort-and-Sweep), "
        "SchedulingService (create/update/delete + pessimistic lock Ruangan->Dosen + capacity check), "
        "dan pengujian Example-Based + Hypothesis Property-Based & Differential Testing."
    ),
    version="0.7.0",
    lifespan=lifespan,
)


@app.exception_handler(KRSError)
async def krs_error_handler(_: Request, exc: KRSError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=exc.body())


@app.exception_handler(ScheduleError)
async def schedule_error_handler(_: Request, exc: ScheduleError) -> JSONResponse:
    """Single exception handler polimorfik untuk `ScheduleError` dan semua turunannya.
    `ScheduleConflictError` menimpa `body()` untuk menyertakan daftar konflik terstruktur.
    """
    return JSONResponse(status_code=exc.status_code, content=exc.body())


app.include_router(krs_router)
app.include_router(schedule_router)


@app.get("/health", tags=["Health"])
def health_check() -> dict[str, str]:
    return {"status": "ok", "module": "jadwal-dan-ruang-minggu-7"}
