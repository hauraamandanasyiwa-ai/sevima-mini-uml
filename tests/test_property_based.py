from datetime import time

from hypothesis import given, settings
from hypothesis import strategies as st

from app.models.krs import MataKuliah
from app.validators import ConflictValidator, KRSContext, MAX_SKS, SKSValidator


def _dummy_mk(idx: int, sks: int, hari: int = 1, mulai: time = time(8, 0), selesai: time = time(10, 0)) -> MataKuliah:
    return MataKuliah(
        kode_mk=f"MK{idx:03d}",
        nama=f"Mata Kuliah {idx}",
        sks=sks,
        hari=hari,
        jam_mulai=mulai,
        jam_selesai=selesai,
    )


@settings(max_examples=1000)
@given(sks_list=st.lists(st.integers(min_value=1, max_value=4), max_size=40))
def test_property_total_sks_never_exceeds_24(sks_list: list[int]) -> None:
    """Properti 1 (1.000 kombinasi acak tanpa DB):
    Berapapun urutan dan jumlah mata kuliah (1..4 SKS, hingga 40 MK) yang dicoba
    dimasukkan lewat SKSValidator:
    1. Total SKS yang diterima TIDAK PERNAH melebihi MAX_SKS (24).
    2. Setiap penolakan WAJIB beralasan: total + sks_baru memang > 24
       (mencegah validator yang asal menolak semua MK lulus tes).
    """
    validator = SKSValidator(max_sks=MAX_SKS)
    accepted: list[MataKuliah] = []

    for idx, sks in enumerate(sks_list):
        candidate = _dummy_mk(idx=idx, sks=sks)
        ctx = KRSContext(
            nim="20240001",
            semester="20251",
            existing_courses=accepted,
            new_course=candidate,
            session=None,  # type: ignore[arg-type]  # SKSValidator murni in-memory
        )
        res = validator.check(ctx)

        if res.ok:
            accepted.append(candidate)
            # Assert 1: total SKS tidak pernah melebihi 24
            assert sum(c.sks for c in accepted) <= MAX_SKS
        else:
            # Assert 2: penolakan wajib beralasan
            assert sum(c.sks for c in accepted) + sks > MAX_SKS


def _occupied_slots(mk: MataKuliah) -> set[tuple[int, int]]:
    """Pemeriksa independen untuk Properti 2 (BUKAN memakai rumus ConflictValidator!):
    Mengubah satu jadwal menjadi himpunan menit-menit yang terpakai pada hari itu.
    Interval half-open [start_min, end_min) sehingga bersambung (10:30-10:30) tidak bertumpuk.
    """
    start_min = mk.jam_mulai.hour * 60 + mk.jam_mulai.minute
    end_min = mk.jam_selesai.hour * 60 + mk.jam_selesai.minute
    return {(mk.hari, minute) for minute in range(start_min, end_min)}


# Strategi jadwal acak pada 3 hari (Senin-Rabu) supaya bentrok sering terjadi
_schedule_strategy = st.tuples(
    st.integers(min_value=1, max_value=3),   # hari: Senin..Rabu
    st.integers(min_value=7, max_value=16),  # jam mulai: 07..16
    st.sampled_from([0, 30]),                # menit mulai: :00 atau :30
    st.sampled_from([60, 90, 120, 150]),     # durasi dalam menit
)


@settings(max_examples=500)
@given(schedules=st.lists(_schedule_strategy, max_size=25))
def test_property_accepted_courses_never_conflict(
    schedules: list[tuple[int, int, int, int]],
) -> None:
    """Properti 2 (500 kombinasi acak jadwal pada 3 hari):
    Seluruh mata kuliah yang lolos ConflictValidator tidak boleh memiliki
    irisan menit yang sama (diperiksa secara independen lewat fungsi himpunan slot).
    """
    validator = ConflictValidator()
    accepted: list[MataKuliah] = []

    for idx, (hari, jam_mulai, menit_mulai, durasi) in enumerate(schedules):
        start_total = jam_mulai * 60 + menit_mulai
        end_total = start_total + durasi
        mulai = time(start_total // 60, start_total % 60)
        selesai = time(end_total // 60, end_total % 60)
        candidate = _dummy_mk(idx=idx, sks=3, hari=hari, mulai=mulai, selesai=selesai)

        ctx = KRSContext(
            nim="20240001",
            semester="20251",
            existing_courses=accepted,
            new_course=candidate,
            session=None,  # type: ignore[arg-type]  # ConflictValidator murni in-memory
        )
        res = validator.check(ctx)
        if res.ok:
            accepted.append(candidate)

    # Verifikasi independen: jumlah slot semua MK == jumlah slot gabungannya (tidak ada irisan)
    all_slot_sets = [_occupied_slots(c) for c in accepted]
    sum_of_sizes = sum(len(s) for s in all_slot_sets)
    union_slots: set[tuple[int, int]] = set().union(*all_slot_sets) if all_slot_sets else set()
    assert sum_of_sizes == len(union_slots)
