import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# Default ke SQLite untuk pengembangan lokal cepat; gunakan MySQL via DATABASE_URL
# Contoh MySQL: mysql+pymysql://root:password@localhost:3306/simak_db
# Catatan: SQLite mengabaikan SELECT ... FOR UPDATE. Uji race condition di MySQL.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./simak_krs.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    connect_args=connect_args,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    class_=Session,
)


class Base(DeclarativeBase):
    """Base class untuk seluruh model SQLAlchemy 2.0."""


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
