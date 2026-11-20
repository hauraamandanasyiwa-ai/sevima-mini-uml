from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from app.models.krs import MataKuliah


@dataclass(frozen=True)
class ValidationResult:
    """Hasil validasi yang immutable (frozen) agar tidak bisa diubah setelah dibuat."""

    ok: bool
    message: str = ""


@dataclass
class KRSContext:
    """Wadah data (context object) yang diteruskan di sepanjang rantai validator.

    Dengan satu objek context, semua validator memiliki tanda tangan method yang
    seragam walaupun kebutuhan datanya berbeda.
    """

    nim: str
    semester: str
    existing_courses: list[MataKuliah]
    new_course: MataKuliah
    session: Session


class Validator(ABC):
    """Kelas abstrak induk untuk pola Chain of Responsibility + Template Method.

    - Logika merantai (`set_next`, `validate`) ditulis sekali di kelas induk.
    - Setiap turunan wajib mengimplementasikan `check(context)` untuk satu aturan saja.
    """

    def __init__(self) -> None:
        self._next: Optional["Validator"] = None

    def set_next(self, validator: "Validator") -> "Validator":
        """Menyimpan validator berikutnya dan mengembalikannya untuk chaining."""
        self._next = validator
        return validator

    def validate(self, context: KRSContext) -> ValidationResult:
        """Mesin rantai (Template Method): berhenti pada kegagalan pertama (fail-fast)."""
        result = self.check(context)
        if not result.ok or self._next is None:
            return result
        return self._next.validate(context)

    @abstractmethod
    def check(self, context: KRSContext) -> ValidationResult:
        """Memeriksa satu aturan bisnis spesifik."""


def build_validation_chain(validators: list[Validator]) -> Optional[Validator]:
    """Merangkai daftar validator secara berurutan dan mengembalikan kepala rantai."""
    if not validators:
        return None
    for idx in range(len(validators) - 1):
        validators[idx].set_next(validators[idx + 1])
    validators[-1]._next = None
    return validators[0]
