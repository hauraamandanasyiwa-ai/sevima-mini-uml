from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import get_db
from app.main import app
from app.models import Base, JalurMasuk, ProgramStudi

SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(test_engine, "connect")
def _enable_sqlite_fk(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


TestingSessionLocal = sessionmaker(
    bind=test_engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


@pytest.fixture()
def db() -> Generator[Session, None, None]:
    """Menyiapkan database SQLite in-memory bersih sebelum setiap tes dan menghapusnya sesudah tes."""
    Base.metadata.create_all(bind=test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture()
def client(db: Session) -> Generator[TestClient, None, None]:
    """Menyediakan TestClient FastAPI dengan dependency override get_db -> session test."""

    def _override_get_db() -> Generator[Session, None, None]:
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def prodi_ti(db: Session) -> ProgramStudi:
    prodi = ProgramStudi(
        kode="001",
        nama="Teknik Informatika",
        fakultas="Fakultas Ilmu Komputer",
    )
    db.add(prodi)
    db.commit()
    db.refresh(prodi)
    return prodi


@pytest.fixture()
def prodi_si(db: Session) -> ProgramStudi:
    prodi = ProgramStudi(
        kode="002",
        nama="Sistem Informasi",
        fakultas="Fakultas Ilmu Komputer",
    )
    db.add(prodi)
    db.commit()
    db.refresh(prodi)
    return prodi


@pytest.fixture()
def jalur_snbp(db: Session) -> JalurMasuk:
    jalur = JalurMasuk(nama="SNBP")
    db.add(jalur)
    db.commit()
    db.refresh(jalur)
    return jalur


@pytest.fixture()
def jalur_snbt(db: Session) -> JalurMasuk:
    jalur = JalurMasuk(nama="SNBT")
    db.add(jalur)
    db.commit()
    db.refresh(jalur)
    return jalur


@pytest.fixture()
def jalur_mandiri(db: Session) -> JalurMasuk:
    jalur = JalurMasuk(nama="Mandiri")
    db.add(jalur)
    db.commit()
    db.refresh(jalur)
    return jalur


def daftar(
    client: TestClient,
    *,
    nama_lengkap: str = "Sinta Dewi",
    email: str = "sinta.dewi@example.com",
    phone: str = "081234567890",
    tanggal_lahir: str = "2007-04-12",
    alamat: str = "Jl. Pendidikan No. 1, Bandung",
    program_studi_id: int = 1,
    jalur_masuk_id: int = 1,
):
    """Fungsi pembantu untuk mengirim POST /api/pmb/register dengan data dummy valid."""
    return client.post(
        "/api/pmb/register",
        json={
            "nama_lengkap": nama_lengkap,
            "email": email,
            "phone": phone,
            "tanggal_lahir": tanggal_lahir,
            "alamat": alamat,
            "program_studi_id": program_studi_id,
            "jalur_masuk_id": jalur_masuk_id,
        },
    )
