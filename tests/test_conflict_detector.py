from datetime import time

import pytest

from app.services.conflict_detector import (
    Conflict,
    JadwalSlot,
    detect_schedule_conflicts,
    detect_schedule_conflicts_naive,
)


def J(
    slot_id: int,
    hari: int,
    mulai: str,
    selesai: str,
    ruang: str,
    dosen: int,
) -> JadwalSlot:
    """Helper singkat untuk membuat JadwalSlot dari teks jam (mis. '08:00', '09:40')."""
    h1, m1 = map(int, mulai.split(":"))
    h2, m2 = map(int, selesai.split(":"))
    return JadwalSlot(
        id=slot_id,
        hari=hari,
        jam_mulai=time(h1, m1),
        jam_selesai=time(h2, m2),
        ruangan_kode=ruang,
        dosen_id=dosen,
    )


# Jadwal acuan pertama selalu sama: Senin 08:00-09:40 di A101 dengan Dosen #1
BASE_SLOT = J(1, 1, "08:00", "09:40", "A101", 1)


@pytest.mark.parametrize(
    ("second", "expected"),
    [
        # 1. Ruangan sama, dosen berbeda, waktu bertumpuk -> room_conflict
        (
            J(2, 1, "09:00", "10:40", "A101", 2),
            {Conflict("room_conflict", (1, 2))},
        ),
        # 2. Dosen sama, ruangan berbeda, waktu bertumpuk -> lecturer_conflict
        (
            J(2, 1, "09:00", "10:40", "B201", 1),
            {Conflict("lecturer_conflict", (1, 2))},
        ),
        # 3. Bersambung tepat pukul 09:40 -> TIDAK bentrok (half-open interval)
        (
            J(2, 1, "09:40", "11:20", "A101", 1),
            set(),
        ),
        # 4. Beda hari, ruangan & dosen sama -> TIDAK bentrok
        (
            J(2, 3, "08:00", "09:40", "A101", 1),
            set(),
        ),
        # 5. Jadwal kedua berada di dalam jadwal pertama, ruang & dosen sama -> 2 konflik sekaligus
        (
            J(2, 1, "08:20", "09:10", "A101", 1),
            {
                Conflict("room_conflict", (1, 2)),
                Conflict("lecturer_conflict", (1, 2)),
            },
        ),
        # 6. Jam sama, ruangan berbeda DAN dosen berbeda -> kondisi normal (TIDAK ada time_overlap)
        (
            J(2, 1, "08:00", "09:40", "B201", 2),
            set(),
        ),
    ],
)
def test_conflict_detector_both_versions_match_examples(
    second: JadwalSlot,
    expected: set[Conflict],
) -> None:
    """Memastikan versi naif dan versi teroptimasi (sort-and-sweep) menangkap
    seluruh 5+1 kasus kunci (penjaga permanen terhadap 5 bug klasik AI).
    """
    schedules = [BASE_SLOT, second]
    assert set(detect_schedule_conflicts_naive(schedules)) == expected
    assert set(detect_schedule_conflicts(schedules)) == expected
