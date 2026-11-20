from app.queries.prerequisite import prasyarat_belum_lulus
from app.validators.base import KRSContext, ValidationResult, Validator


class PrerequisiteValidator(Validator):
    """Validator 4: memastikan seluruh mata kuliah prasyarat telah lulus
    pada semester sebelumnya dengan nilai minimal C.

    Tidak menulis query SQL sendiri, melainkan mendelegasikan ke fungsi
    `prasyarat_belum_lulus` di lapisan queries.
    """

    def check(self, context: KRSContext) -> ValidationResult:
        missing = prasyarat_belum_lulus(
            session=context.session,
            nim=context.nim,
            kode_mk=context.new_course.kode_mk,
            semester_aktif=context.semester,
        )
        if missing:
            daftar_nama = ", ".join(missing)
            return ValidationResult(
                ok=False,
                message=f"Prasyarat tidak terpenuhi untuk {context.new_course.nama}: {daftar_nama}.",
            )
        return ValidationResult(ok=True)
