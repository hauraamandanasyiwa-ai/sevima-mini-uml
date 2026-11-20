from app.models.krs import MataKuliah
from app.validators.base import KRSContext, ValidationResult, Validator

NAMA_HARI: dict[int, str] = {
    1: "Senin",
    2: "Selasa",
    3: "Rabu",
    4: "Kamis",
    5: "Jumat",
    6: "Sabtu",
}


def is_schedule_conflict(mk1: MataKuliah, mk2: MataKuliah) -> bool:
    """Rumus irisan interval jadwal:
    Dua jadwal bentrok jika dan hanya jika harinya sama DAN
    (mulai1 < selesai2) DAN (mulai2 < selesai1).

    Menangkap seluruh kasus:
    - Bertumpuk sebagian (misal 08:00-10:30 vs 09:00-11:00)
    - Satu jadwal di dalam jadwal lain (misal 08:00-12:00 vs 09:00-10:00)
    - Jam persis sama (misal 08:00-10:00 vs 08:00-10:00)

    Keputusan desain:
    - Jadwal bersambung (selesai 10:30, mulai berikutnya 10:30) TIDAK bentrok
      karena menggunakan `<` bukan `<=`.
    """
    if mk1.hari != mk2.hari:
        return False
    return mk1.jam_mulai < mk2.jam_selesai and mk2.jam_mulai < mk1.jam_selesai


class ConflictValidator(Validator):
    """Validator 3: memeriksa bentrok jadwal mata kuliah baru terhadap KRS saat ini."""

    def check(self, context: KRSContext) -> ValidationResult:
        target = context.new_course
        for existing in context.existing_courses:
            if is_schedule_conflict(target, existing):
                hari_str = NAMA_HARI.get(target.hari, f"Hari-{target.hari}")
                return ValidationResult(
                    ok=False,
                    message=(
                        f"Jadwal {target.nama} ({hari_str} "
                        f"{target.jam_mulai.strftime('%H:%M')}-{target.jam_selesai.strftime('%H:%M')}) "
                        f"bentrok dengan {existing.nama} ({hari_str} "
                        f"{existing.jam_mulai.strftime('%H:%M')}-{existing.jam_selesai.strftime('%H:%M')})."
                    ),
                )
        return ValidationResult(ok=True)
