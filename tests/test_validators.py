from datetime import time

import pytest
from sqlalchemy.orm import Session

from app.models.krs import KRS, KRSDetail, KRSStatus, MataKuliah
from app.validators import (
    ConflictValidator,
    DuplicateValidator,
    KRSContext,
    MAX_SKS,
    PrerequisiteValidator,
    SKSValidator,
    build_validation_chain,
    is_schedule_conflict,
)


def _mk(kode: str, nama: str, sks: int, hari: int, mulai: time, selesai: time) -> MataKuliah:
    return MataKuliah(
        kode_mk=kode,
        nama=nama,
        sks=sks,
        hari=hari,
        jam_mulai=mulai,
        jam_selesai=selesai,
    )


def test_self_referencing_prerequisite_direction(db_session: Session) -> None:
    """Memastikan primaryjoin & secondaryjoin tidak terbalik:
    Struktur Data membutuhkan Algoritma, BUKAN sebaliknya.
    """
    struktur_data = db_session.get(MataKuliah, "IF201")
    algoritma = db_session.get(MataKuliah, "IF101")
    assert struktur_data is not None and algoritma is not None
    assert [p.kode_mk for p in struktur_data.prasyarat] == ["IF101"]
    assert algoritma.prasyarat == []


def test_duplicate_validator(db_session: Session) -> None:
    basis_data = db_session.get(MataKuliah, "IF202")
    assert basis_data is not None

    ctx = KRSContext(
        nim="20240001",
        semester="20251",
        existing_courses=[basis_data],
        new_course=basis_data,
        session=db_session,
    )
    res = DuplicateValidator().check(ctx)
    assert not res.ok
    assert "Basis Data" in res.message
    assert "sudah ada di KRS" in res.message


def test_sks_validator_allows_exact_24_and_rejects_over(db_session: Session) -> None:
    existing_21 = [
        _mk(f"MK{i}", f"Mata Kuliah {i}", 3, (i % 6) + 1, time(8, 0), time(10, 0))
        for i in range(7)  # 7 * 3 = 21 SKS
    ]
    mk_3 = _mk("MK8", "Pemrograman Web", 3, 5, time(13, 0), time(15, 30))
    mk_4 = _mk("MK9", "Proyek Akhir", 4, 5, time(13, 0), time(16, 0))

    # Tepat 24 SKS -> diizinkan
    res_24 = SKSValidator().check(
        KRSContext("20240001", "20251", existing_21, mk_3, db_session)
    )
    assert res_24.ok

    # 25 SKS -> ditolak dengan angka eksplisit
    res_25 = SKSValidator().check(
        KRSContext("20240001", "20251", existing_21, mk_4, db_session)
    )
    assert not res_25.ok
    assert "25" in res_25.message
    assert str(MAX_SKS) in res_25.message


@pytest.mark.parametrize(
    ("hari1", "m1", "s1", "hari2", "m2", "s2", "expected"),
    [
        # Bertumpuk sebagian: Basis Data 08:00-10:30 vs Statistika 09:00-11:00
        (1, time(8, 0), time(10, 30), 1, time(9, 0), time(11, 0), True),
        # Satu jadwal berada di dalam jadwal lain
        (1, time(8, 0), time(12, 0), 1, time(9, 0), time(10, 0), True),
        # Jam persis sama
        (2, time(8, 0), time(10, 0), 2, time(8, 0), time(10, 0), True),
        # Bersambung tepat (selesai 10:30, mulai 10:30) -> TIDAK bentrok (< bukan <=)
        (1, time(8, 0), time(10, 30), 1, time(10, 30), time(13, 0), False),
        # Hari berbeda, jam sama -> TIDAK bentrok
        (1, time(8, 0), time(10, 30), 2, time(8, 0), time(10, 30), False),
    ],
)
def test_schedule_conflict_cases(
    hari1: int,
    m1: time,
    s1: time,
    hari2: int,
    m2: time,
    s2: time,
    expected: bool,
) -> None:
    mk1 = _mk("A", "MK A", 3, hari1, m1, s1)
    mk2 = _mk("B", "MK B", 3, hari2, m2, s2)
    assert is_schedule_conflict(mk1, mk2) is expected
    assert is_schedule_conflict(mk2, mk1) is expected


def test_conflict_validator_message_mentions_course_names(db_session: Session) -> None:
    basis_data = db_session.get(MataKuliah, "IF202")
    statistika = db_session.get(MataKuliah, "IF203")
    assert basis_data is not None and statistika is not None

    ctx = KRSContext("20240001", "20251", [basis_data], statistika, db_session)
    res = ConflictValidator().check(ctx)
    assert not res.ok
    assert "Statistika" in res.message
    assert "Basis Data" in res.message


def test_prerequisite_validator_grade_weights_and_previous_semester(db_session: Session) -> None:
    """Menguji query NOT EXISTS + skala_nilai:
    - Belum ambil -> gagal
    - Nilai D (bobot 1.00) -> gagal (bukan lulus karena string 'D' > 'C'!)
    - Nilai A di semester SAMA (20251) -> gagal (harus semester sebelumnya)
    - Nilai C (bobot 2.00) / B / A di semester sebelumnya (20242 < 20251) -> lulus
    """
    struktur_data = db_session.get(MataKuliah, "IF201")
    assert struktur_data is not None
    validator = PrerequisiteValidator()

    # 1. Budi belum pernah mengambil Algoritma (IF101)
    ctx = KRSContext("20240001", "20251", [], struktur_data, db_session)
    res_none = validator.check(ctx)
    assert not res_none.ok
    assert "Algoritma dan Pemrograman" in res_none.message

    # 2. Budi mengambil Algoritma di 20241 tapi nilai D (tidak lulus)
    krs_20241 = KRS(nim="20240001", semester="20241", status=KRSStatus.APPROVED)
    db_session.add(krs_20241)
    db_session.flush()
    db_session.add(KRSDetail(krs_id=krs_20241.id, kode_mk="IF101", nilai="D"))
    db_session.commit()

    res_d = validator.check(ctx)
    assert not res_d.ok
    assert "Algoritma dan Pemrograman" in res_d.message

    # 3. Budi mengulang di semester yang SAMA (20251) dengan nilai A -> belum dihitung
    krs_20251 = KRS(nim="20240001", semester="20251", status=KRSStatus.DRAFT)
    db_session.add(krs_20251)
    db_session.flush()
    db_session.add(KRSDetail(krs_id=krs_20251.id, kode_mk="IF101", nilai="A"))
    db_session.commit()

    res_same_sem = validator.check(ctx)
    assert not res_same_sem.ok

    # 4. Budi lulus Algoritma di 20242 dengan nilai C (bobot 2.00) -> LULUS
    krs_20242 = KRS(nim="20240001", semester="20242", status=KRSStatus.APPROVED)
    db_session.add(krs_20242)
    db_session.flush()
    db_session.add(KRSDetail(krs_id=krs_20242.id, kode_mk="IF101", nilai="C"))
    db_session.commit()

    res_pass = validator.check(ctx)
    assert res_pass.ok


def test_chain_stops_at_first_failure(db_session: Session) -> None:
    """Memastikan rantai berhenti di DuplicateValidator tanpa pesan SKS/Conflict."""
    basis_data = db_session.get(MataKuliah, "IF202")
    assert basis_data is not None

    chain = build_validation_chain(
        [DuplicateValidator(), SKSValidator(max_sks=3), ConflictValidator()]
    )
    assert chain is not None

    ctx = KRSContext("20240001", "20251", [basis_data], basis_data, db_session)
    res = chain.validate(ctx)
    assert not res.ok
    assert "sudah ada di KRS" in res.message
