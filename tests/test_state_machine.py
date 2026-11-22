from itertools import product

import pytest

from app.exceptions import TransitionError
from app.models.krs import KRS, KRSStatus

# 6 transisi sah ditulis ULANG secara manual dari spesifikasi (Minggu 6 + Minggu 8)
# (BUKAN diambil dari KRS_TRANSITIONS di kode produksi agar bug tidak ikut tersalin).
VALID_TRANSITIONS: set[tuple[KRSStatus, KRSStatus, str]] = {
    (KRSStatus.DRAFT, KRSStatus.SUBMITTED, "mahasiswa"),
    (KRSStatus.SUBMITTED, KRSStatus.APPROVED, "dosen_pa"),
    (KRSStatus.SUBMITTED, KRSStatus.REVISION, "dosen_pa"),
    (KRSStatus.REVISION, KRSStatus.SUBMITTED, "mahasiswa"),
    # Minggu 8: aktor sistem mengembalikan KRS terdampak perubahan jadwal ke REVISION
    (KRSStatus.SUBMITTED, KRSStatus.REVISION, "system"),
    (KRSStatus.APPROVED, KRSStatus.REVISION, "system"),
}

ALL_COMBINATIONS: list[tuple[KRSStatus, KRSStatus, str]] = list(
    product(KRSStatus, KRSStatus, ["mahasiswa", "dosen_pa", "system"])
)

ILLEGAL_TRANSITIONS: list[tuple[KRSStatus, KRSStatus, str]] = [
    combo for combo in ALL_COMBINATIONS if combo not in VALID_TRANSITIONS
]


def test_total_transition_combinations_is_48() -> None:
    """Memastikan 4 state x 4 state x 3 aktor = 48 kombinasi (6 sah + 42 ilegal)."""
    assert len(ALL_COMBINATIONS) == 48
    assert len(VALID_TRANSITIONS) == 6
    assert len(ILLEGAL_TRANSITIONS) == 42


@pytest.mark.parametrize(
    ("source", "target", "actor"),
    sorted(VALID_TRANSITIONS, key=lambda x: (x[0].value, x[1].value, x[2])),
)
def test_valid_transitions_succeed(
    source: KRSStatus,
    target: KRSStatus,
    actor: str,
) -> None:
    krs = KRS(nim="20240001", semester="20251", status=source)
    krs.transition(target, actor)
    assert krs.status == target


@pytest.mark.parametrize(
    ("source", "target", "actor"),
    ILLEGAL_TRANSITIONS,
)
def test_all_42_illegal_transitions_raise_and_preserve_status(
    source: KRSStatus,
    target: KRSStatus,
    actor: str,
) -> None:
    """Bukti kriteria sukses: state transition tidak bisa di-skip
    (termasuk DRAFT -> APPROVED, REVISION -> APPROVED, serta system -> APPROVED).
    """
    krs = KRS(nim="20240001", semester="20251", status=source)
    with pytest.raises(TransitionError, match="Transisi tidak diizinkan"):
        krs.transition(target, actor)
    # Status tidak boleh berubah sedikit pun ketika transisi gagal
    assert krs.status == source
