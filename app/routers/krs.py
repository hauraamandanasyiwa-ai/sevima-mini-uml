from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.exceptions import KRSError
from app.schemas.krs import (
    AddCourseRequest,
    KRSDetailOut,
    KRSOut,
    ValidateKRSResponse,
    ValidationIssueOut,
)
from app.services.krs_manager import KRSManager

router = APIRouter(prefix="/krs", tags=["KRS"])


def get_krs_manager(db: Session = Depends(get_db)) -> KRSManager:
    return KRSManager(session=db)


@router.get("/{nim}/{semester}", response_model=KRSOut)
def get_krs(
    nim: str,
    semester: str,
    manager: KRSManager = Depends(get_krs_manager),
) -> KRSOut:
    """Endpoint tipis: mengambil data KRS beserta daftar mata kuliahnya."""
    try:
        krs = manager.get_krs(nim=nim, semester=semester)
    except KRSError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    total_sks = sum(d.mata_kuliah.sks for d in krs.details)
    return KRSOut(
        id=krs.id,
        nim=krs.nim,
        semester=krs.semester,
        status=krs.status.value,
        dosen_pa_id=krs.dosen_pa_id,
        total_sks=total_sks,
        details=[KRSDetailOut.model_validate(d) for d in krs.details],
    )


@router.post(
    "/{nim}/{semester}/courses",
    response_model=KRSDetailOut,
    status_code=status.HTTP_201_CREATED,
)
def add_course(
    nim: str,
    semester: str,
    payload: AddCourseRequest,
    manager: KRSManager = Depends(get_krs_manager),
) -> KRSDetailOut:
    """Endpoint tipis: menambahkan satu mata kuliah ke KRS mahasiswa."""
    try:
        detail = manager.add_course(
            nim=nim,
            semester=semester,
            kode_mk=payload.kode_mk,
        )
    except KRSError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    return KRSDetailOut.model_validate(detail)


@router.delete(
    "/{nim}/{semester}/courses/{kode_mk}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_course(
    nim: str,
    semester: str,
    kode_mk: str,
    manager: KRSManager = Depends(get_krs_manager),
) -> None:
    """Endpoint tipis: menghapus satu mata kuliah dari KRS mahasiswa."""
    try:
        manager.remove_course(nim=nim, semester=semester, kode_mk=kode_mk)
    except KRSError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/{nim}/{semester}/validate", response_model=ValidateKRSResponse)
def validate_krs(
    nim: str,
    semester: str,
    manager: KRSManager = Depends(get_krs_manager),
) -> ValidateKRSResponse:
    """Endpoint tipis: memvalidasi keseluruhan KRS dan mengumpulkan semua error."""
    try:
        failures = manager.validate_krs(nim=nim, semester=semester)
    except KRSError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    return ValidateKRSResponse(
        valid=len(failures) == 0,
        errors=[ValidationIssueOut(ok=f.ok, message=f.message) for f in failures],
    )
