from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.routers.pmb import router as pmb_router

app = FastAPI(
    title="API Modul PMB (Penerimaan Mahasiswa Baru)",
    description=(
        "Implementasi Minggu 3 Mata Kuliah Pemrograman Berorientasi Objek: "
        "SQLAlchemy 2.0, Alembic Migration, dan REST API FastAPI."
    ),
    version="0.1.0",
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    _request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Mengubah error validasi Pydantic (default 422) menjadi 400 Bad Request
    sesuai keputusan teknis di ADR-001 agar konsisten dengan spesifikasi tes tugas,
    tanpa membocorkan stack trace internal."""
    errors = [
        {
            "field": ".".join(str(loc) for loc in err.get("loc", []) if loc != "body"),
            "message": err.get("msg", "Input tidak valid"),
        }
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "detail": "Validasi input gagal",
            "errors": errors,
        },
    )


@app.get("/", tags=["Health"])
def root() -> dict[str, str]:
    return {"message": "API Modul PMB aktif. Buka /docs untuk Swagger UI."}


app.include_router(pmb_router)
