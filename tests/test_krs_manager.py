import pytest
from sqlalchemy.orm import Session

from app.exceptions import (
    CourseNotFoundError,
    KRSNotFoundError,
    KRSStatusError,
    KRSValidationError,
    MahasiswaNotFoundError,
)
from app.models.krs import KRS, KRSDetail, KRSStatus
from app.services.krs_manager import KRSManager
from app.validators import KRSContext, ValidationResult, Validator


class AlwaysFailValidator(Validator):
    """Fake validator untuk membuktikan Dependency Injection pada KRSManager."""

    def check(self, context: KRSContext) -> ValidationResult:
        return ValidationResult(ok=False, message="Tunggakan SPP belum lunas.")


def test_add_and_remove_course_flow(db_session: Session) -> None:
    manager = KRSManager(session=db_session)

    # Tambah Basis Data (Senin 08:00-10:30)
    detail1 = manager.add_course("20240001", "20251", "IF202")
    assert detail1.kode_mk == "IF202"

    # Tambah Jaringan Komputer (Senin 10:30-13:00 — bersambung, tidak bentrok)
    detail2 = manager.add_course("20240001", "20251", "IF204")
    assert detail2.kode_mk == "IF204"

    # Tambah Statistika (Senin 09:00-11:00 — bentrok dengan Basis Data & Jaringan)
    with pytest.raises(KRSValidationError, match="bentrok"):
        manager.add_course("20240001", "20251", "IF203")

    # Hapus Basis Data
    manager.remove_course("20240001", "20251", "IF202")
    krs = manager.get_krs("20240001", "20251")
    assert [d.kode_mk for d in krs.details] == ["IF204"]


def test_status_guard_blocks_submitted_and_approved(db_session: Session) -> None:
    krs = KRS(nim="20240001", semester="20251", status=KRSStatus.SUBMITTED)
    db_session.add(krs)
    db_session.commit()

    manager = KRSManager(session=db_session)
    with pytest.raises(KRSStatusError, match="submitted"):
        manager.add_course("20240001", "20251", "IF202")

    # Ubah ke REVISION -> kembali diizinkan
    krs.status = KRSStatus.REVISION
    db_session.commit()
    detail = manager.add_course("20240001", "20251", "IF202")
    assert detail.kode_mk == "IF202"


def test_add_course_unknown_nim_or_course(db_session: Session) -> None:
    manager = KRSManager(session=db_session)

    with pytest.raises(MahasiswaNotFoundError):
        manager.add_course("99999999", "20251", "IF202")

    with pytest.raises(CourseNotFoundError):
        manager.add_course("20240001", "20251", "ZZ999")

    with pytest.raises(KRSNotFoundError):
        manager.remove_course("20240002", "20251", "IF202")


def test_validate_krs_collects_all_errors(db_session: Session) -> None:
    """Memastikan validate_krs mengumpulkan SEMUA kesalahan sekaligus (ADR-001):
    - IF202 (Basis Data) bentrok dengan IF203 (Statistika)
    - IF201 (Struktur Data) prasyarat Algoritma belum terpenuhi
    """
    krs = KRS(nim="20240001", semester="20251", status=KRSStatus.DRAFT)
    db_session.add(krs)
    db_session.flush()
    db_session.add_all(
        [
            KRSDetail(krs_id=krs.id, kode_mk="IF202"),
            KRSDetail(krs_id=krs.id, kode_mk="IF203"),
            KRSDetail(krs_id=krs.id, kode_mk="IF201"),
        ]
    )
    db_session.commit()

    manager = KRSManager(session=db_session)
    failures = manager.validate_krs("20240001", "20251")

    messages = [f.message for f in failures]
    assert any("bentrok" in m for m in messages)
    assert any("Prasyarat tidak terpenuhi" in m for m in messages)
    assert len(failures) >= 2


def test_dependency_injection_open_closed_principle(db_session: Session) -> None:
    """Membuktikan aturan baru (misal Tunggakan SPP) bisa dipasang tanpa mengubah KRSManager."""
    manager = KRSManager(session=db_session, validators=[AlwaysFailValidator()])
    with pytest.raises(KRSValidationError, match="Tunggakan SPP"):
        manager.add_course("20240001", "20251", "IF202")
