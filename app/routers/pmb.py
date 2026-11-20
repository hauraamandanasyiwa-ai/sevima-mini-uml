from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.pmb import PendaftarOut, RegisterRequest
from app.services.pmb_service import (
    EmailAlreadyRegisteredError,
    InvalidReferenceError,
    PMBService,
)

router = APIRouter(prefix="/api/pmb", tags=["PMB"])


@router.post(
    "/register",
    response_model=PendaftarOut,
    status_code=status.HTTP_201_CREATED,
    summary="Mendaftarkan calon mahasiswa baru",
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
