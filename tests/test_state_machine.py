from itertools import product

import pytest

from app.exceptions import TransitionError
from app.models.krs import KRS, KRSStatus

# 4 transisi sah ditulis ULANG secara manual dari spesifikasi dokumen tugas
# (BUKAN diambil dari KRS_TRANSITIONS di kode produksi agar bug tidak ikut tersalin).
VALID_TRANSITIONS: set[tuple[KRSStatus, KRSStatus, str]] = {
    (KRSStatus.DRAFT, KRSStatus.SUBMITTED, "mahasiswa"),
    (KRSStatus.SUBMITTED, KRSStatus.APPROVED, "dosen_pa"),
    (KRSStatus.SUBMITTED, KRSStatus.REVISION, "dosen_pa"),
    (KRSStatus.REVISION, KRSStatus.SUBMITTED, "mahasiswa"),
}

ALL_COMBINATIONS: list[tuple[KRSStatus, KRSStatus, str]] = list(
    product(KRSStatus, KRSStatus, ["mahasiswa", "dosen_pa"])
)

ILLEGAL_TRANSITIONS: list[tuple[KRSStatus, KRSStatus, str]] = [
    combo for combo in ALL_COMBINATIONS if combo not in VALID_TRANSITIONS
]


def test_total_transition_combinations_is_32() -> None:
    """Memastikan 4 state x 4 state x 2 aktor = 32 kombinasi (4 sah + 28 ilegal)."""
    assert len(ALL_COMBINATIONS) == 32
    assert len(VALID_TRANSITIONS) == 4
    assert len(ILLEGAL_TRANSITIONS) == 28


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
def test_all_28_illegal_transitions_raise_and_preserve_status(
    source: KRSStatus,
    target: KRSStatus,
    actor: str,
) -> None:
    """Bukti kriteria sukses: state transition tidak bisa di-skip
    (termasuk DRAFT -> APPROVED dan REVISION -> APPROVED).
    """
    krs = KRS(nim="20240001", semester="20251", status=source)
    with pytest.raises(TransitionError, match="Transisi tidak diizinkan"):
        krs.transition(target, actor)
    # Status tidak boleh berubah sedikit pun ketika transisi gagal
    assert krs.status == source
