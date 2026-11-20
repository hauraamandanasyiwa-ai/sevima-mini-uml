from contextlib import asynccontextmanager
from datetime import time

from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import Base, SessionLocal, engine
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
    """Mengisi data dummy (Budi, Siti, dan mata kuliah contoh) secara idempoten
    agar seluruh skenario KRS bisa langsung diuji di Swagger UI (/docs).
    """
    if session.get(Mahasiswa, "20240001") is None:
        session.add(Mahasiswa(nim="20240001", nama="Budi Santoso", prodi="Teknik Informatika"))
    if session.get(Mahasiswa, "20240002") is None:
        session.add(Mahasiswa(nim="20240002", nama="Siti Rahma", prodi="Teknik Informatika"))

    courses_spec = [
        ("IF101", "Algoritma dan Pemrograman", 3, 1, time(8, 0), time(10, 30)),
        ("MA101", "Kalkulus 1", 3, 2, time(8, 0), time(10, 30)),
        ("IF201", "Struktur Data", 3, 3, time(8, 0), time(10, 30)),
        ("MA201", "Kalkulus 2", 3, 4, time(8, 0), time(10, 30)),
        ("IF202", "Basis Data", 3, 1, time(8, 0), time(10, 30)),
        ("IF203", "Statistika", 3, 1, time(9, 0), time(11, 0)),
        ("IF204", "Jaringan Komputer", 3, 1, time(10, 30), time(13, 0)),
    ]
    for kode, nama, sks, hari, mulai, selesai in courses_spec:
        if session.get(MataKuliah, kode) is None:
            session.add(
                MataKuliah(
                    kode_mk=kode,
                    nama=nama,
                    sks=sks,
                    hari=hari,
                    jam_mulai=mulai,
                    jam_selesai=selesai,
                )
            )
    session.flush()

    # Relasi prasyarat: Struktur Data -> Algoritma, Kalkulus 2 -> Kalkulus 1
    algoritma = session.get(MataKuliah, "IF101")
    kalkulus1 = session.get(MataKuliah, "MA101")
    struktur_data = session.get(MataKuliah, "IF201")
    kalkulus2 = session.get(MataKuliah, "MA201")

    if struktur_data and algoritma and algoritma not in struktur_data.prasyarat:
        struktur_data.prasyarat.append(algoritma)
    if kalkulus2 and kalkulus1 and kalkulus1 not in kalkulus2.prasyarat:
        kalkulus2.prasyarat.append(kalkulus1)

    # Riwayat semester lalu (20242):
    # - Budi lulus Kalkulus 1 (B), tapi nilai Algoritma = D (belum lulus prasyarat IF201)
    budi_prev = session.scalars(
        select(KRS).where(KRS.nim == "20240001", KRS.semester == "20242")
    ).first()
    if budi_prev is None:
        budi_prev = KRS(nim="20240001", semester="20242", status=KRSStatus.APPROVED)
        session.add(budi_prev)
        session.flush()
        session.add_all(
            [
                KRSDetail(krs_id=budi_prev.id, kode_mk="MA101", nilai="B"),
                KRSDetail(krs_id=budi_prev.id, kode_mk="IF101", nilai="D"),
            ]
        )

    # - Siti lulus Algoritma (C) -> memenuhi prasyarat Struktur Data (IF201)
    siti_prev = session.scalars(
        select(KRS).where(KRS.nim == "20240002", KRS.semester == "20242")
    ).first()
    if siti_prev is None:
        siti_prev = KRS(nim="20240002", semester="20242", status=KRSStatus.APPROVED)
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
    title="SIMAK Mini — Modul KRS (Minggu 5)",
    description=(
        "Implementasi Modul Kartu Rencana Studi (KRS): Skema 4 tabel + skala nilai, "
        "KRS Manager Service (with_for_update + single transaction), "
        "Chain of Responsibility (4 Validator), dan Query Prasyarat NOT EXISTS."
    ),
    version="0.5.0",
    lifespan=lifespan,
)

app.include_router(krs_router)


@app.get("/health", tags=["Health"])
def health_check() -> dict[str, str]:
    return {"status": "ok", "module": "krs-minggu-5"}
