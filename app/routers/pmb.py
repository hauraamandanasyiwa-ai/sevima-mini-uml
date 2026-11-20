from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.pmb import PMBStatsOut, PendaftarOut, RegisterRequest, StatusOut
from app.services.nim_generator import InvalidNIMDataError, NIMCapacityExceededError
from app.services.pmb_service import (
    ApplicantNotFoundError,
    EmailAlreadyRegisteredError,
    InvalidReferenceError,
    InvalidStatusTransitionError,
    PMBService,
)

router = APIRouter(prefix="/api/pmb", tags=["PMB"])


@router.post(
    "/register",
    response_model=PendaftarOut,
    status_code=status.HTTP_201_CREATED,
    summary="Mendaftarkan calon mahasiswa baru",
    description="Mendaftarkan pendaftar baru dengan status awal `pending`.",
    responses={
        400: {"description": "Format input atau referensi (prodi/jalur masuk) tidak valid"},
        409: {"description": "Email sudah terdaftar"},
    },
)
def register_calon_mahasiswa(
    payload: RegisterRequest,
    db: Session = Depends(get_db),
) -> PendaftarOut:
    try:
        calon = PMBService.register(db=db, data=payload)
    except EmailAlreadyRegisteredError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except InvalidReferenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return PendaftarOut.model_validate(calon)


@router.put(
    "/approve/{pendaftar_id}",
    response_model=PendaftarOut,
    status_code=status.HTTP_200_OK,
    summary="Menyetujui pendaftar dan men-generate NIM",
    description=(
        "Mengubah status pendaftar dari `pending` menjadi `approved`, mencatat `approved_at` (UTC), "
        "dan men-generate NIM 11 digit (`YYYYPPPNNNN`). Bersifat idempotent: memanggil approve "
        "ulang pada pendaftar yang sudah `approved` mengembalikan NIM yang sama tanpa membuat NIM baru."
    ),
    responses={
        400: {"description": "Data pendaftar tidak valid untuk pembuatan NIM (mis. kode prodi bukan 3 digit)"},
        404: {"description": "Pendaftar tidak ditemukan"},
        409: {"description": "Konflik status (pendaftar sudah berstatus rejected atau kapasitas NIM penuh)"},
    },
)
def approve_calon_mahasiswa(
    pendaftar_id: int,
    db: Session = Depends(get_db),
) -> PendaftarOut:
    try:
        calon = PMBService.approve(db=db, pendaftar_id=pendaftar_id)
    except ApplicantNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except InvalidNIMDataError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except (InvalidStatusTransitionError, NIMCapacityExceededError) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return PendaftarOut.model_validate(calon)


@router.put(
    "/reject/{pendaftar_id}",
    response_model=PendaftarOut,
    status_code=status.HTTP_200_OK,
    summary="Menolak pendaftar",
    description=(
        "Mengubah status pendaftar dari `pending` menjadi `rejected`. "
        "Pendaftar yang sudah `approved` tidak dapat ditolak (`409 Conflict`)."
    ),
    responses={
        404: {"description": "Pendaftar tidak ditemukan"},
        409: {"description": "Pendaftar sudah berstatus approved dan tidak dapat ditolak"},
    },
)
def reject_calon_mahasiswa(
    pendaftar_id: int,
    db: Session = Depends(get_db),
) -> PendaftarOut:
    try:
        calon = PMBService.reject(db=db, pendaftar_id=pendaftar_id)
    except ApplicantNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except InvalidStatusTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return PendaftarOut.model_validate(calon)


@router.get(
    "/status/{pendaftar_id}",
    response_model=StatusOut,
    status_code=status.HTTP_200_OK,
    summary="Mengecek status pendaftaran calon mahasiswa",
    description="Mengembalikan status dan NIM (jika sudah diterima) tanpa mengekspos data pribadi sensitif.",
    responses={
        404: {"description": "Pendaftar tidak ditemukan"},
    },
)
def get_status_pendaftar(
    pendaftar_id: int,
    db: Session = Depends(get_db),
) -> StatusOut:
    try:
        return PMBService.get_status(db=db, pendaftar_id=pendaftar_id)
    except ApplicantNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get(
    "/stats",
    response_model=PMBStatsOut,
    status_code=status.HTTP_200_OK,
    summary="Statistik pendaftar PMB untuk dashboard admin",
    description=(
        "Menghitung jumlah pendaftar total, per status, per program studi, dan per jalur masuk "
        "menggunakan agregasi SQL (`COUNT`, `GROUP BY`, `OUTER JOIN`)."
    ),
)
def get_pmb_stats(db: Session = Depends(get_db)) -> PMBStatsOut:
    return PMBService.get_stats(db=db)
