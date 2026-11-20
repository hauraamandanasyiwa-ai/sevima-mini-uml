import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exceptions import (
    ForbiddenError,
    KRSError,
    KRSLockedError,
    KRSValidationError,
    TransitionError,
)
from app.models.krs import KRS, KRSApprovalLog, KRSStatus, Notifikasi
from app.services.krs_manager import KRSManager


def test_example_kalkulus_2_without_kalkulus_1_fails_with_clear_message(
    db_session: Session,
) -> None:
    """Tes wajib dokumen tugas #1:
    Menambah Kalkulus 2 tanpa lulus Kalkulus 1 harus gagal dengan pesan prasyarat yang jelas.
    """
    manager = KRSManager(session=db_session)
    with pytest.raises(KRSValidationError) as exc_info:
        manager.add_course("20240001", "20251", "MA201")

    msg = exc_info.value.message
    assert "Prasyarat tidak terpenuhi" in msg
    assert "Kalkulus 1" in msg


def test_example_two_monday_0800_courses_conflict(db_session: Session) -> None:
    """Tes wajib dokumen tugas #2:
    Dua mata kuliah di hari Senin jam 08:00 (IF101 & IF202) harus ditolak sebagai bentrok.
    """
    manager = KRSManager(session=db_session)
    manager.add_course("20240001", "20251", "IF101")

    with pytest.raises(KRSValidationError) as exc_info:
        manager.add_course("20240001", "20251", "IF202")

    msg = exc_info.value.message
    assert "bentrok" in msg.lower()
    assert "Basis Data" in msg
    assert "Algoritma" in msg


def test_full_lifecycle_draft_submit_revise_resubmit_approve(db_session: Session) -> None:
    """Alur lengkap State Machine + audit log + notifikasi DB dalam transaksi."""
    manager = KRSManager(session=db_session)

    # 1. Budi menambah Basis Data (draft, version naik)
    manager.add_course("20240001", "20251", "IF202")
    krs = manager.get_krs("20240001", "20251")
    assert krs.status == KRSStatus.DRAFT
    assert krs.dosen_pa_id == "PA001"
    v_after_add = krs.version

    # 2. Budi submit KRS -> SUBMITTED
    krs = manager.submit_krs("20240001", "20251", actor_nim="20240001")
    assert krs.status == KRSStatus.SUBMITTED
    assert krs.submitted_at is not None
    assert krs.version > v_after_add

    # Saat SUBMITTED, add/remove harus terkunci (409 KRSLockedError)
    with pytest.raises(KRSLockedError):
        manager.add_course("20240001", "20251", "IF204")

    # 3. Dosen PA meminta revisi -> REVISION
    krs = manager.revise_krs(
        "20240001",
        "20251",
        dosen_pa_id="PA001",
        catatan="Tambahkan Jaringan Komputer.",
        expected_version=krs.version,
    )
    assert krs.status == KRSStatus.REVISION
    assert krs.revision_note == "Tambahkan Jaringan Komputer."

    # 4. Saat REVISION, Budi boleh menambah Jaringan Komputer lalu submit ulang
    manager.add_course("20240001", "20251", "IF204")
    krs = manager.submit_krs("20240001", "20251")
    assert krs.status == KRSStatus.SUBMITTED

    # 5. Dosen PA menyetujui -> APPROVED (1 transaksi: status + approved_at + log + notifikasi)
    krs = manager.approve_krs(
        "20240001",
        "20251",
        dosen_pa_id="PA001",
        expected_version=krs.version,
    )
    assert krs.status == KRSStatus.APPROVED
    assert krs.approved_at is not None

    logs = db_session.scalars(
        select(KRSApprovalLog).where(KRSApprovalLog.krs_id == krs.id)
    ).all()
    assert [log.action for log in logs] == ["submit", "revise", "submit", "approve"]

    notifs = db_session.scalars(select(Notifikasi).where(Notifikasi.krs_id == krs.id)).all()
    assert len(notifs) == 2
    assert any("Disetujui" in n.judul for n in notifs)


def test_authorization_two_layers_wrong_dosen_pa_gets_403(db_session: Session) -> None:
    """Lapis 2 otorisasi: dosen PA lain (PA999) tidak boleh approve/revise KRS Budi."""
    manager = KRSManager(session=db_session)
    manager.add_course("20240001", "20251", "IF202")
    manager.submit_krs("20240001", "20251")

    with pytest.raises(ForbiddenError) as exc_info:
        manager.approve_krs("20240001", "20251", dosen_pa_id="PA999")
    assert exc_info.value.status_code == 403

    with pytest.raises(ForbiddenError):
        manager.revise_krs("20240001", "20251", dosen_pa_id="PA999", catatan="Coba revise")

    # Mahasiswa lain juga tidak boleh submit KRS Budi
    with pytest.raises(ForbiddenError):
        manager.submit_krs("20240001", "20251", actor_nim="20240002")


def test_empty_krs_cannot_be_submitted_and_double_submit_raises_409(
    db_session: Session,
) -> None:
    krs = KRS(nim="20240001", semester="20251", status=KRSStatus.DRAFT, dosen_pa_id="PA001")
    db_session.add(krs)
    db_session.commit()

    manager = KRSManager(session=db_session)
    with pytest.raises(KRSError, match="kosong"):
        manager.submit_krs("20240001", "20251")

    manager.add_course("20240001", "20251", "IF202")
    manager.submit_krs("20240001", "20251")

    # Submit kedua kali -> TransitionError (409)
    with pytest.raises(TransitionError) as exc_info:
        manager.submit_krs("20240001", "20251")
    assert exc_info.value.status_code == 409


def test_revise_requires_non_empty_note(db_session: Session) -> None:
    manager = KRSManager(session=db_session)
    manager.add_course("20240001", "20251", "IF202")
    manager.submit_krs("20240001", "20251")

    with pytest.raises(KRSError, match="Catatan revisi"):
        manager.revise_krs("20240001", "20251", dosen_pa_id="PA001", catatan="   ")


def test_optimistic_locking_rejects_stale_version(db_session: Session) -> None:
    """Melindungi dari layar basi (stale screen): jika KRS sudah berubah sejak
    halaman dibuka dosen, approve dengan versi lama ditolak dengan 409 KRSLockedError.
    """
    manager = KRSManager(session=db_session)
    manager.add_course("20240001", "20251", "IF202")
    krs = manager.submit_krs("20240001", "20251")
    stale_version = krs.version - 1

    with pytest.raises(KRSLockedError, match="versi") as exc_info:
        manager.approve_krs(
            "20240001",
            "20251",
            dosen_pa_id="PA001",
            expected_version=stale_version,
        )
    assert exc_info.value.status_code == 409


def test_approve_transaction_atomicity_rolls_back_on_failure(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Membuktikan Atomicity (ACID): jika penyimpanan Notifikasi gagal di tengah
    `approve_krs`, maka status KRS tetap SUBMITTED, `approved_at` tetap None,
    dan `KRSApprovalLog` ikut ter-rollback (tidak pernah tercatat setengah jadi).
    """
    manager = KRSManager(session=db_session)
    manager.add_course("20240001", "20251", "IF202")
    krs = manager.submit_krs("20240001", "20251")
    krs_id = krs.id

    original_add = db_session.add

    def failing_add(instance, *args, **kwargs):
        if isinstance(instance, Notifikasi):
            raise RuntimeError("Simulasi kegagalan DB saat menyimpan notifikasi")
        return original_add(instance, *args, **kwargs)

    monkeypatch.setattr(db_session, "add", failing_add)

    with pytest.raises(RuntimeError, match="Simulasi kegagalan DB"):
        manager.approve_krs("20240001", "20251", dosen_pa_id="PA001")

    db_session.expire_all()
    refreshed = db_session.get(KRS, krs_id)
    assert refreshed is not None
    assert refreshed.status == KRSStatus.SUBMITTED
    assert refreshed.approved_at is None

    approve_logs = db_session.scalars(
        select(KRSApprovalLog).where(
            KRSApprovalLog.krs_id == krs_id,
            KRSApprovalLog.action == "approve",
        )
    ).all()
    assert approve_logs == []
