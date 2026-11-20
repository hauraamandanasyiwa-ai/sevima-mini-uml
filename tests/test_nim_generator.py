import pytest
from sqlalchemy.orm import Session

from app.models.nim_counter import NimCounter
from app.services.nim_generator import (
    InvalidNIMDataError,
    NIMCapacityExceededError,
    format_nim,
    generate_nim,
)


def test_format_nim_valid_zero_padding() -> None:
    """Unit test murni (tanpa DB) untuk memverifikasi format 11 digit dan zero-padding 4 digit."""
    assert format_nim(2025, "001", 1) == "20250010001"
    assert format_nim(2025, "001", 42) == "20250010042"
    assert format_nim(2026, "002", 9999) == "20260029999"


@pytest.mark.parametrize("bad_kode", ["", "1", "01", "0001", "ABC", "01A"])
def test_format_nim_invalid_kode_prodi(bad_kode: str) -> None:
    with pytest.raises(InvalidNIMDataError):
        format_nim(2025, bad_kode, 1)


@pytest.mark.parametrize("bad_tahun", [999, 10000, -2025])
def test_format_nim_invalid_tahun(bad_tahun: int) -> None:
    with pytest.raises(InvalidNIMDataError):
        format_nim(bad_tahun, "001", 1)


@pytest.mark.parametrize("bad_seq", [0, -1, 10000])
def test_format_nim_invalid_nomor_urut(bad_seq: int) -> None:
    with pytest.raises(InvalidNIMDataError):
        format_nim(2025, "001", bad_seq)


def test_generate_nim_reset_per_tahun_dan_prodi(db: Session) -> None:
    """Nomor urut harus dihitung ulang per kombinasi (tahun, kode_prodi)."""
    # Arrange & Act
    nim_ti_1 = generate_nim(db, tahun=2025, kode_prodi="001")
    nim_ti_2 = generate_nim(db, tahun=2025, kode_prodi="001")
    nim_si_1 = generate_nim(db, tahun=2025, kode_prodi="002")
    nim_ti_2026_1 = generate_nim(db, tahun=2026, kode_prodi="001")
    db.commit()

    # Assert
    assert nim_ti_1 == "20250010001"
    assert nim_ti_2 == "20250010002"
    assert nim_si_1 == "20250020001"
    assert nim_ti_2026_1 == "20260010001"


def test_generate_nim_invalid_inputs_raise(db: Session) -> None:
    with pytest.raises(InvalidNIMDataError):
        generate_nim(db, tahun=2025, kode_prodi="12")

    with pytest.raises(InvalidNIMDataError):
        generate_nim(db, tahun=99, kode_prodi="001")


def test_generate_nim_capacity_exceeded(db: Session) -> None:
    """Jika counter sudah mencapai 9999, generator wajib menolak agar tidak melampaui 4 digit."""
    # Arrange
    db.add(NimCounter(tahun=2025, kode_prodi="001", last_number=9999))
    db.commit()

    # Act & Assert
    with pytest.raises(NIMCapacityExceededError):
        generate_nim(db, tahun=2025, kode_prodi="001")
