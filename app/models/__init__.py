from app.models.base import Base
from app.models.calon_mahasiswa import CalonMahasiswa, StatusPMB
from app.models.jalur_masuk import JalurMasuk
from app.models.program_studi import ProgramStudi

__all__ = [
    "Base",
    "ProgramStudi",
    "JalurMasuk",
    "CalonMahasiswa",
    "StatusPMB",
]
