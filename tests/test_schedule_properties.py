from collections import Counter
from datetime import time

from hypothesis import given, settings
from hypothesis import strategies as st

from app.services.conflict_detector import (
    JadwalSlot,
    detect_schedule_conflicts,
    detect_schedule_conflicts_naive,
)

# Strategi sempit agar bentrok sering terjadi:
# - Hari: Senin..Rabu (1..3)
# - Jam mulai: 07..16 (jam bulat)
# - Durasi: 1..3 jam
# - 2 ruangan (A101, B201) dan 3 dosen (1, 2, 3)
_raw_slot_strategy = st.tuples(
    st.integers(min_value=1, max_value=3),
    st.integers(min_value=7, max_value=16),
    st.integers(min_value=1, max_value=3),
    st.sampled_from(["A101", "B201"]),
    st.integers(min_value=1, max_value=3),
)


def _build_slots(raw_items: list[tuple[int, int, int, str, int]]) -> list[JadwalSlot]:
    return [
        JadwalSlot(
            id=idx + 1,
            hari=hari,
            jam_mulai=time(mulai, 0),
            jam_selesai=time(mulai + durasi, 0),
            ruangan_kode=ruang,
            dosen_id=dosen,
        )
        for idx, (hari, mulai, durasi, ruang, dosen) in enumerate(raw_items)
    ]


@settings(max_examples=300)
@given(raw_items=st.lists(_raw_slot_strategy, max_size=25))
def test_property_accepted_schedules_never_have_room_or_lecturer_conflict(
    raw_items: list[tuple[int, int, int, str, int]],
) -> None:
    """Properti 1 (Hypothesis):
    Simulasi admin memasukkan jadwal satu per satu; jadwal hanya diterima jika
    `detect_schedule_conflicts` tidak menemukan konflik.
    Verifikasi INDEPENDEN: pecah tiap jadwal menjadi slot 1-jam per ruangan dan
    per dosen lalu hitung dengan Counter -> tidak boleh ada slot dengan count > 1.
    """
    candidates = _build_slots(raw_items)
    accepted: list[JadwalSlot] = []

    for candidate in candidates:
        trial = [*accepted, candidate]
        if not detect_schedule_conflicts(trial):
            accepted.append(candidate)

    room_slots: Counter[tuple[int, str, int]] = Counter()
    lecturer_slots: Counter[tuple[int, int, int]] = Counter()

    for s in accepted:
        for hour in range(s.jam_mulai.hour, s.jam_selesai.hour):
            room_slots[(s.hari, s.ruangan_kode, hour)] += 1
            lecturer_slots[(s.hari, s.dosen_id, hour)] += 1

    assert all(count == 1 for count in room_slots.values())
    assert all(count == 1 for count in lecturer_slots.values())


@settings(max_examples=300)
@given(raw_items=st.lists(_raw_slot_strategy, max_size=25))
def test_property_differential_sweep_matches_naive_exactly(
    raw_items: list[tuple[int, int, int, str, int]],
) -> None:
    """Properti 2 (Differential Testing):
    Versi teroptimasi (`detect_schedule_conflicts`) dan versi acuan naif
    (`detect_schedule_conflicts_naive`) harus menghasilkan Counter konflik yang
    PERSIS SAMA termasuk jumlah kemunculannya (menangkap pasangan ganda).
    """
    slots = _build_slots(raw_items)
    naive_counts = Counter(detect_schedule_conflicts_naive(slots))
    sweep_counts = Counter(detect_schedule_conflicts(slots))
    assert sweep_counts == naive_counts
