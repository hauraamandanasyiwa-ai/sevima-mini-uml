from typing import Optional

from fastapi import APIRouter, Body, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.krs import KRS
from app.schemas.krs import (
    AddCourseRequest,
    ApproveKRSRequest,
    KRSDetailOut,
    KRSOut,
    MataKuliahOut,
    RecommendKRSRequest,
    RecommendKRSResponse,
    ReviseKRSRequest,
    SubmitKRSRequest,
    ValidateKRSResponse,
    ValidationIssueOut,
)
from app.services.krs_manager import KRSManager
from app.services.krs_recommender import KRSRecommender

router = APIRouter(prefix="/krs", tags=["KRS"])


def get_krs_manager(db: Session = Depends(get_db)) -> KRSManager:
    return KRSManager(session=db)


def get_krs_recommender(db: Session = Depends(get_db)) -> KRSRecommender:
    return KRSRecommender(session=db)


def _to_krs_out(krs: KRS) -> KRSOut:
    total_sks = sum(d.mata_kuliah.sks for d in krs.details)
    return KRSOut(
        id=krs.id,
        nim=krs.nim,
        semester=krs.semester,
        status=krs.status.value,
        dosen_pa_id=krs.dosen_pa_id,
        submitted_at=krs.submitted_at,
        approved_at=krs.approved_at,
        revision_note=krs.revision_note,
        version=krs.version,
        total_sks=total_sks,
        details=[KRSDetailOut.model_validate(d) for d in krs.details],
    )


@router.get("/{nim}/{semester}", response_model=KRSOut)
def get_krs(
    nim: str,
    semester: str,
    manager: KRSManager = Depends(get_krs_manager),
) -> KRSOut:
    """Mengambil data KRS beserta daftar mata kuliah, status, dan versi terkini."""
    return _to_krs_out(manager.get_krs(nim=nim, semester=semester))


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
    """Menambahkan satu mata kuliah ke KRS mahasiswa."""
    detail = manager.add_course(nim=nim, semester=semester, kode_mk=payload.kode_mk)
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
    """Menghapus satu mata kuliah dari KRS mahasiswa."""
    manager.remove_course(nim=nim, semester=semester, kode_mk=kode_mk)


@router.get("/{nim}/{semester}/validate", response_model=ValidateKRSResponse)
def validate_krs(
    nim: str,
    semester: str,
    manager: KRSManager = Depends(get_krs_manager),
) -> ValidateKRSResponse:
    """Memvalidasi keseluruhan KRS dan mengumpulkan seluruh kesalahan sekaligus."""
    failures = manager.validate_krs(nim=nim, semester=semester)
    return ValidateKRSResponse(
        valid=len(failures) == 0,
        errors=[ValidationIssueOut(ok=f.ok, message=f.message) for f in failures],
    )


@router.post("/{nim}/{semester}/submit", response_model=KRSOut)
def submit_krs(
    nim: str,
    semester: str,
    payload: Optional[SubmitKRSRequest] = Body(default=None),
    manager: KRSManager = Depends(get_krs_manager),
) -> KRSOut:
    """Mengajukan KRS mahasiswa (DRAFT/REVISION -> SUBMITTED)."""
    actor_nim = payload.actor_nim if payload else None
    krs = manager.submit_krs(nim=nim, semester=semester, actor_nim=actor_nim)
    return _to_krs_out(krs)


@router.post("/{nim}/{semester}/approve", response_model=KRSOut)
def approve_krs(
    nim: str,
    semester: str,
    payload: ApproveKRSRequest,
    manager: KRSManager = Depends(get_krs_manager),
) -> KRSOut:
    """Menyetujui KRS oleh Dosen PA (SUBMITTED -> APPROVED) dalam 1 transaksi ACID."""
    krs = manager.approve_krs(
        nim=nim,
        semester=semester,
        dosen_pa_id=payload.dosen_pa_id,
        expected_version=payload.version,
    )
    return _to_krs_out(krs)


@router.post("/{nim}/{semester}/revise", response_model=KRSOut)
def revise_krs(
    nim: str,
    semester: str,
    payload: ReviseKRSRequest,
    manager: KRSManager = Depends(get_krs_manager),
) -> KRSOut:
    """Mengembalikan KRS ke mahasiswa untuk revisi (SUBMITTED -> REVISION)."""
    krs = manager.revise_krs(
        nim=nim,
        semester=semester,
        dosen_pa_id=payload.dosen_pa_id,
        catatan=payload.catatan,
        expected_version=payload.version,
    )
    return _to_krs_out(krs)


@router.post("/{nim}/{semester}/recommend", response_model=RecommendKRSResponse)
def recommend_krs(
    nim: str,
    semester: str,
    payload: RecommendKRSRequest,
    recommender: KRSRecommender = Depends(get_krs_recommender),
) -> RecommendKRSResponse:
    """Challenge Opsional: Rekomendasi kombinasi KRS bebas bentrok (CSP Backtracking
    + Guardrail Validator)."""
    rec = recommender.recommend(
        nim=nim,
        semester=semester,
        desired_kode_mk=payload.desired_kode_mk,
        target_sks=payload.target_sks,
    )
    return RecommendKRSResponse(
        total_sks=rec.total_sks,
        selected_courses=[MataKuliahOut.model_validate(m) for m in rec.selected_courses],
        skipped_reasons=rec.skipped_reasons,
    )
