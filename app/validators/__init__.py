from app.validators.base import (
    KRSContext,
    ValidationResult,
    Validator,
    build_validation_chain,
)
from app.validators.conflict import ConflictValidator, is_schedule_conflict
from app.validators.duplicate import DuplicateValidator
from app.validators.prerequisite import PrerequisiteValidator
from app.validators.sks import MAX_SKS, SKSValidator


def default_validators() -> list[Validator]:
    """Urutan rantai validasi yang disarankan:
    1. DuplicateValidator   — termurah (in-memory), pesan tepat jika MK sudah ada
    2. SKSValidator         — in-memory, batas maksimal 24 SKS
    3. ConflictValidator    — in-memory, rumus irisan interval jadwal
    4. PrerequisiteValidator — query DB (NOT EXISTS), dijalankan paling akhir
    """
    return [
        DuplicateValidator(),
        SKSValidator(),
        ConflictValidator(),
        PrerequisiteValidator(),
    ]


__all__ = [
    "ValidationResult",
    "KRSContext",
    "Validator",
    "build_validation_chain",
    "DuplicateValidator",
    "SKSValidator",
    "MAX_SKS",
    "ConflictValidator",
    "is_schedule_conflict",
    "PrerequisiteValidator",
    "default_validators",
]
