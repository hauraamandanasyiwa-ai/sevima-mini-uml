from app.validators.base import KRSContext, ValidationResult, Validator

# Satu sumber kebenaran untuk batas maksimal SKS per semester
MAX_SKS = 24


class SKSValidator(Validator):
    """Validator 2: memastikan total SKS per semester tidak melebihi MAX_SKS (24).

    Total tepat 24 SKS masih diizinkan; hanya > 24 SKS yang ditolak.
    """

    def __init__(self, max_sks: int = MAX_SKS) -> None:
        super().__init__()
        self.max_sks = max_sks

    def check(self, context: KRSContext) -> ValidationResult:
        current_sks = sum(course.sks for course in context.existing_courses)
        projected_sks = current_sks + context.new_course.sks

        if projected_sks > self.max_sks:
            return ValidationResult(
                ok=False,
                message=(
                    f"Total SKS {projected_sks} melebihi batas {self.max_sks} "
                    f"(saat ini {current_sks} SKS + {context.new_course.nama} "
                    f"{context.new_course.sks} SKS)."
                ),
            )
        return ValidationResult(ok=True)
