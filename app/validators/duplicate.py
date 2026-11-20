from app.validators.base import KRSContext, ValidationResult, Validator


class DuplicateValidator(Validator):
    """Validator 1 (paling depan): mencegah double enrollment dalam satu KRS.

    Diletakkan paling awal karena paling murah (tanpa query tambahan) dan
    memberikan pesan paling tepat saat mahasiswa tanpa sengaja menambah MK
    yang sudah ada di KRS, bukan pesan 'SKS melebihi batas'.
    """

    def check(self, context: KRSContext) -> ValidationResult:
        target = context.new_course
        for existing in context.existing_courses:
            if existing.kode_mk == target.kode_mk:
                return ValidationResult(
                    ok=False,
                    message=(
                        f"Mata kuliah {target.nama} ({target.kode_mk}) "
                        "sudah ada di KRS semester ini."
                    ),
                )
        return ValidationResult(ok=True)
