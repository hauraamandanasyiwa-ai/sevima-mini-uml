from datetime import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.krs import DEFAULT_SKALA_NILAI, MataKuliah, SkalaNilai
from app.models.mahasiswa import Mahasiswa


def _seed_test_db(session: Session) -> None:
    for huruf, bobot in DEFAULT_SKALA_NILAI.items():
        session.add(SkalaNilai(huruf=huruf, bobot=bobot))

    session.add(
        Mahasiswa(
            nim="20240001",
            nama="Budi Santoso",
            prodi="Teknik Informatika",
            dosen_pa_id="PA001",
        )
    )
    session.add(
        Mahasiswa(
            nim="20240002",
            nama="Siti Rahma",
            prodi="Teknik Informatika",
            dosen_pa_id="PA002",
        )
    )

    algoritma = MataKuliah(
        kode_mk="IF101",
        nama="Algoritma dan Pemrograman",
        sks=3,
        hari=1,
        jam_mulai=time(8, 0),
        jam_selesai=time(10, 30),
        is_wajib=True,
    )
    kalkulus1 = MataKuliah(
        kode_mk="MA101",
        nama="Kalkulus 1",
        sks=3,
        hari=2,
        jam_mulai=time(8, 0),
        jam_selesai=time(10, 30),
        is_wajib=True,
    )
    struktur_data = MataKuliah(
        kode_mk="IF201",
        nama="Struktur Data",
        sks=3,
        hari=3,
        jam_mulai=time(8, 0),
        jam_selesai=time(10, 30),
        is_wajib=True,
        prasyarat=[algoritma],
    )
    kalkulus2 = MataKuliah(
        kode_mk="MA201",
        nama="Kalkulus 2",
        sks=3,
        hari=4,
        jam_mulai=time(8, 0),
        jam_selesai=time(10, 30),
        is_wajib=True,
        prasyarat=[kalkulus1],
    )
    basis_data = MataKuliah(
        kode_mk="IF202",
        nama="Basis Data",
        sks=3,
        hari=1,
        jam_mulai=time(8, 0),
        jam_selesai=time(10, 30),
        is_wajib=True,
    )
    statistika = MataKuliah(
        kode_mk="IF203",
        nama="Statistika",
        sks=3,
        hari=1,
        jam_mulai=time(9, 0),
        jam_selesai=time(11, 0),
        is_wajib=False,
    )
    jaringan = MataKuliah(
        kode_mk="IF204",
        nama="Jaringan Komputer",
        sks=3,
        hari=1,
        jam_mulai=time(10, 30),
        jam_selesai=time(13, 0),
        is_wajib=True,
    )

    session.add_all(
        [algoritma, kalkulus1, struktur_data, kalkulus2, basis_data, statistika, jaringan]
    )
    session.commit()


@pytest.fixture
def db_session() -> Session:
    """In-memory SQLite session untuk unit & integration test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    with TestingSession() as session:
        _seed_test_db(session)
        yield session


@pytest.fixture
def api_client(db_session: Session) -> TestClient:
    """FastAPI TestClient yang berbagi DB test in-memory yang sama."""

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
