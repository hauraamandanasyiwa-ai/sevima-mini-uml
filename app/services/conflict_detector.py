from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import time
from itertools import combinations
from typing import Literal, Protocol

ConflictType = Literal["room_conflict", "lecturer_conflict"]


class ScheduleLike(Protocol):
    """Protocol yang dipenuhi baik oleh `JadwalSlot` (ringan, tanpa DB) maupun
    model ORM `Jadwal` (SQLAlchemy).
    """

    id: int
    hari: int
    jam_mulai: time
    jam_selesai: time
    ruangan_kode: str
    dosen_id: int


@dataclass(frozen=True)
class JadwalSlot:
    """Representasi ringan satu slot jadwal tanpa ketergantungan database."""

    id: int
    hari: int
    jam_mulai: time
    jam_selesai: time
    ruangan_kode: str
    dosen_id: int


@dataclass(frozen=True)
class Conflict:
    """Hasil deteksi konflik yang immutable (frozen) agar bisa dimasukkan ke `set`
    dan dihitung dengan `collections.Counter`.

    Hanya ada dua tipe konflik sah: `room_conflict` dan `lecturer_conflict`.
    Irisan waktu saja tanpa ruang atau dosen yang sama BUKAN konflik.
    """

    type: ConflictType
    affected: tuple[int, int]


def pasangan(id1: int, id2: int) -> tuple[int, int]:
    """Mengurutkan pasangan ID jadwal sehingga (A, B) dan (B, A) menghasilkan
    objek `Conflict` yang identik.
    """
    return (id1, id2) if id1 <= id2 else (id2, id1)


def is_time_overlap(a: ScheduleLike, b: ScheduleLike) -> bool:
    """Aturan interval setengah terbuka [jam_mulai, jam_selesai):
    Bertumpuk jika hari sama DAN a.jam_mulai < b.jam_selesai DAN b.jam_mulai < a.jam_selesai.

    Kuliah bersambung (mis. 08:00-09:40 dan 09:40-11:20) TIDAK dianggap bertumpuk
    karena menggunakan `<` bukan `<=`.
    """
    if a.hari != b.hari:
        return False
    return a.jam_mulai < b.jam_selesai and b.jam_mulai < a.jam_selesai


def detect_schedule_conflicts_naive(schedules: Sequence[ScheduleLike]) -> list[Conflict]:
    """Versi 1 (Naif, O(n^2)): memeriksa setiap pasangan unik dengan `itertools.combinations`.

    Sengaja dipertahankan sebagai acuan (oracle) untuk differential testing
    terhadap versi teroptimasi.
    """
    conflicts: list[Conflict] = []
    for a, b in combinations(schedules, 2):
        if not is_time_overlap(a, b):
            continue
        pair = pasangan(a.id, b.id)
        if a.ruangan_kode == b.ruangan_kode:
            conflicts.append(Conflict(type="room_conflict", affected=pair))
        if a.dosen_id == b.dosen_id:
            conflicts.append(Conflict(type="lecturer_conflict", affected=pair))
    return conflicts


# Kamus aturan pengelompokan sehingga satu loop sweep melayani dua dimensi konflik
_GROUP_KEYS: dict[ConflictType, Callable[[ScheduleLike], tuple[int, object]]] = {
    "room_conflict": lambda s: (s.hari, s.ruangan_kode),
    "lecturer_conflict": lambda s: (s.hari, s.dosen_id),
}


def detect_schedule_conflicts(schedules: Sequence[ScheduleLike]) -> list[Conflict]:
    """Versi 2 (Teroptimasi: Grouping + Sort-and-Sweep, O(n log n + k)).

    1. Kelompokkan jadwal berdasarkan `(hari, ruangan_kode)` untuk bentrok ruangan
       dan `(hari, dosen_id)` untuk bentrok dosen.
    2. Di setiap kelompok, urutkan jadwal berdasarkan `(jam_mulai, jam_selesai, id)`.
    3. Sapu dari pagi ke sore sambil menyimpan daftar `active`; buang jadwal yang
       sudah selesai pada/sebelum jam mulai jadwal baru (`act.jam_selesai > cur.jam_mulai`,
       memakai `>` bukan `>=` demi kuliah bersambung).
    """
    conflicts: list[Conflict] = []

    for conflict_type, key_fn in _GROUP_KEYS.items():
        groups: dict[tuple[int, object], list[ScheduleLike]] = defaultdict(list)
        for item in schedules:
            groups[key_fn(item)].append(item)

        for bucket in groups.values():
            if len(bucket) < 2:
                continue
            ordered = sorted(bucket, key=lambda s: (s.jam_mulai, s.jam_selesai, s.id))
            active: list[ScheduleLike] = []

            for cur in ordered:
                # Pertahankan hanya jadwal yang masih berlangsung melewati jam_mulai `cur`
                active = [act for act in active if act.jam_selesai > cur.jam_mulai]
                for act in active:
                    conflicts.append(
                        Conflict(type=conflict_type, affected=pasangan(act.id, cur.id))
                    )
                active.append(cur)

    return conflicts
