"""Mengisi data referensi awal (program_studi & jalur_masuk) secara idempotent."""

from sqlalchemy import select

from app.database import SessionLocal
from app.models import JalurMasuk, ProgramStudi


def seed_reference_data() -> None:
    db = SessionLocal()
    try:
        default_prodi = [
            {"kode": "001", "nama": "Teknik Informatika", "fakultas": "Fakultas Ilmu Komputer"},
            {"kode": "002", "nama": "Sistem Informasi", "fakultas": "Fakultas Ilmu Komputer"},
            {"kode": "003", "nama": "Teknik Elektro", "fakultas": "Fakultas Teknik"},
        ]
        for item in default_prodi:
            exists = db.scalar(select(ProgramStudi).where(ProgramStudi.kode == item["kode"]))
            if exists is None:
                db.add(ProgramStudi(**item))

        default_jalur = ["SNBP", "SNBT", "Mandiri"]
        for nama in default_jalur:
            exists = db.scalar(select(JalurMasuk).where(JalurMasuk.nama == nama))
            if exists is None:
                db.add(JalurMasuk(nama=nama))

        db.commit()
        print("Seeding data referensi program_studi & jalur_masuk berhasil.")
    finally:
        db.close()


if __name__ == "__main__":
    seed_reference_data()
