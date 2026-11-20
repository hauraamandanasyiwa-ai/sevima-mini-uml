from contextlib import asynccontextmanager
from datetime import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import Base, SessionLocal, engine
from app.exceptions import KRSError
from app.models.krs import (
    DEFAULT_SKALA_NILAI,
    KRS,
    KRSDetail,
    KRSStatus,
    MataKuliah,
    SkalaNilai,
)
from app.models.mahasiswa import Mahasiswa
from app.routers.krs import router as krs_router


def seed_skala_nilai(session: Session) -> None:
    """Mengisi tabel skala_nilai jika belum ada agar query prasyarat siap pakai."""
    for huruf, bobot in DEFAULT_SKALA_NILAI.items():
        if session.get(SkalaNilai, huruf) is None:
            session.add(SkalaNilai(huruf=huruf, bobot=bobot))
    session.commit()


def seed_dummy_data(session: Session) -> None:
    """Mengisi data dummy (Budi PA001, Siti PA002, dan mata kuliah contoh) secara
    idempoten agar seluruh skenario Minggu 5 & 6 bisa langsung diuji di /docs.
    """
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


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        seed_skala_nilai(session)
        seed_dummy_data(session)
    yield


app = FastAPI(
    title="SIMAK Mini — Modul KRS (Minggu 6)",
    description=(
        "Modul KRS Lengkap (Minggu 5 & 6): State Machine 4 status dengan tabel transisi, "
        "Otorisasi 2 lapis (peran + kepemilikan Dosen PA), Transaction Management ACID "
        "(pessimistic + optimistic locking `version`), Chain of Responsibility 4 Validator, "
        "Property-Based Testing (Hypothesis), dan Challenge Opsional KRS Recommendation CSP."
    ),
    version="0.6.0",
    lifespan=lifespan,
)


@app.exception_handler(KRSError)
async def krs_error_handler(_: Request, exc: KRSError) -> JSONResponse:
    """Single exception handler polimorfik untuk `KRSError` dan semua turunannya:
    - ForbiddenError  -> 403
    - TransitionError -> 409
    - KRSLockedError  -> 409
    - *NotFoundError  -> 404
    - KRSError / KRSValidationError -> 400
    """
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


app.include_router(krs_router)


@app.get("/health", tags=["Health"])
def health_check() -> dict[str, str]:
    return {"status": "ok", "module": "krs-minggu-6"}
