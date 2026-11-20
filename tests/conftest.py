from datetime import time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.models.krs import DEFAULT_SKALA_NILAI, MataKuliah, SkalaNilai
from app.models.mahasiswa import Mahasiswa


@pytest.fixture
def db_session() -> Session:
    """In-memory SQLite session dengan skema lengkap dan data dummy (Budi & MK contoh).

    Catatan: SQLite cocok untuk unit test logika bisnis & query prasyarat.
    Untuk pengujian race condition `SELECT ... FOR UPDATE`, jalankan di MySQL.
    """
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    with TestingSession() as session:
        # Seed skala nilai
        for huruf, bobot in DEFAULT_SKALA_NILAI.items():
            session.add(SkalaNilai(huruf=huruf, bobot=bobot))

        # Seed mahasiswa dummy (approved dari PMB)
        session.add(Mahasiswa(nim="20240001", nama="Budi Santoso", prodi="Teknik Informatika"))
        session.add(Mahasiswa(nim="20240002", nama="Siti Rahma", prodi="Teknik Informatika"))

        # Seed mata kuliah dummy
        algoritma = MataKuliah(
            kode_mk="IF101",
            nama="Algoritma dan Pemrograman",
            sks=3,
            hari=1,
            jam_mulai=time(8, 0),
            jam_selesai=time(10, 30),
        )
        kalkulus1 = MataKuliah(
            kode_mk="MA101",
            nama="Kalkulus 1",
            sks=3,
            hari=2,
            jam_mulai=time(8, 0),
            jam_selesai=time(10, 30),
        )
        struktur_data = MataKuliah(
            kode_mk="IF201",
            nama="Struktur Data",
            sks=3,
            hari=3,
            jam_mulai=time(8, 0),
            jam_selesai=time(10, 30),
            prasyarat=[algoritma],
        )
        kalkulus2 = MataKuliah(
            kode_mk="MA201",
            nama="Kalkulus 2",
            sks=3,
            hari=4,
            jam_mulai=time(8, 0),
            jam_selesai=time(10, 30),
            prasyarat=[kalkulus1],
        )
        basis_data = MataKuliah(
            kode_mk="IF202",
            nama="Basis Data",
            sks=3,
            hari=1,
            jam_mulai=time(8, 0),
            jam_selesai=time(10, 30),
        )
        statistika = MataKuliah(
            kode_mk="IF203",
            nama="Statistika",
            sks=3,
            hari=1,
            jam_mulai=time(9, 0),
            jam_selesai=time(11, 0),
        )
        jaringan = MataKuliah(
            kode_mk="IF204",
            nama="Jaringan Komputer",
            sks=3,
            hari=1,
            jam_mulai=time(10, 30),
            jam_selesai=time(13, 0),
        )

        session.add_all(
            [algoritma, kalkulus1, struktur_data, kalkulus2, basis_data, statistika, jaringan]
        )
        session.commit()
        yield session
