from app.models.krs import (
    DEFAULT_SKALA_NILAI,
    EDITABLE_KRS_STATUSES,
    KRS,
    KRSDetail,
    KRSStatus,
    MataKuliah,
    SkalaNilai,
    prerequisites,
)
from app.models.mahasiswa import Mahasiswa

__all__ = [
    "Mahasiswa",
    "MataKuliah",
    "prerequisites",
    "KRSStatus",
    "EDITABLE_KRS_STATUSES",
    "KRS",
    "KRSDetail",
    "SkalaNilai",
    "DEFAULT_SKALA_NILAI",
]
