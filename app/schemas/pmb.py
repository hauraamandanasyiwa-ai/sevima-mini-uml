from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.calon_mahasiswa import StatusPMB

INDONESIAN_PHONE_PATTERN = r"^(\+62|62|0)8[1-9][0-9]{6,10}$"


class RegisterRequest(BaseModel):
    """Skema validasi input pendaftaran calon mahasiswa."""

    nama_lengkap: str = Field(
        ...,
        min_length=3,
        max_length=150,
        examples=["Siti Rahmawati"],
    )
    email: EmailStr = Field(
        ...,
        examples=["siti.rahmawati@example.com"],
    )
    phone: str = Field(
        ...,
        pattern=INDONESIAN_PHONE_PATTERN,
        description="Nomor HP Indonesia diawali 08, 628, atau +628",
        examples=["081234567890"],
    )
    tanggal_lahir: date = Field(
        ...,
        examples=["2007-05-14"],
    )
    alamat: str = Field(
        ...,
        min_length=5,
        examples=["Jl. Merdeka No. 10, Bandung"],
    )
    program_studi_id: int = Field(..., gt=0, examples=[1])
    jalur_masuk_id: int = Field(..., gt=0, examples=[1])


class PendaftarOut(BaseModel):
    """Skema response pendaftar tanpa membocorkan data sensitif (alamat & tanggal lahir)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    nama_lengkap: str
    email: EmailStr
    phone: str
    program_studi_id: int
    jalur_masuk_id: int
    status: StatusPMB
    nim: str | None = None
    created_at: datetime
    approved_at: datetime | None = None


class StatusOut(BaseModel):
    """Skema response publik untuk cek status pendaftaran (GET /api/pmb/status/{id}).

    Sengaja membatasi kolom output agar data pribadi (alamat, tanggal lahir,
    email, nomor telepon) tidak ikut terekspos pada endpoint pengecekan status.
    """

    id: int
    nama_lengkap: str
    program_studi: str
    jalur_masuk: str
    status: StatusPMB
    nim: str | None = None
    created_at: datetime
    approved_at: datetime | None = None


class ProdiStatOut(BaseModel):
    """Jumlah pendaftar per program studi."""

    kode: str
    nama: str
    jumlah: int


class JalurStatOut(BaseModel):
    """Jumlah pendaftar per jalur masuk."""

    nama: str
    jumlah: int


class PMBStatsOut(BaseModel):
    """Skema response statistik dashboard admin PMB (GET /api/pmb/stats)."""

    total_pendaftar: int
    per_status: dict[str, int]
    per_program_studi: list[ProdiStatOut]
    per_jalur_masuk: list[JalurStatOut]
