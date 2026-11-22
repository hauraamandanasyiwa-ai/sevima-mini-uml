from typing import Optional

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.grade import Grade
from app.models.krs import MataKuliah
from app.models.mahasiswa import Mahasiswa
from app.schemas.grade import (
    GradeHistoryOut,
    GradeInput,
    GradeMutationResponse,
    GradeOut,
    GradeReferenceDataResponse,
    GradeUpdateInput,
    TranscriptCourseOut,
    TranscriptResponse,
    TranscriptSemesterOut,
)
from app.services.gpa_calculator import (
    calculate_ipk,
    calculate_ips,
    get_transcript,
    tentukan_predikat,
)
from app.services.grade_service import GradeService
from app.services.transcript_html import (
    export_transcript_to_csv,
    render_transcript_html,
)
from app.services.transcript_pdf import generate_transcript_pdf

router = APIRouter(tags=["Grades & Transcripts (Minggu 9-10)"])


def get_grade_service(db: Session = Depends(get_db)) -> GradeService:
    return GradeService(session=db)


def _to_grade_out(g: Grade) -> GradeOut:
    return GradeOut(
        id=g.id,
        nim=g.nim,
        kode_mk=g.kode_mk,
        nama_mk=g.mata_kuliah.nama if g.mata_kuliah else g.kode_mk,
        sks=g.mata_kuliah.sks if g.mata_kuliah else 0,
        semester=g.semester,
        nilai_huruf=g.nilai_huruf,
        nilai_angka=g.nilai_angka,
        presensi_persen=g.presensi_persen,
        updated_by=g.updated_by,
        updated_at=g.updated_at,
    )


@router.get("/grades/reference", response_model=GradeReferenceDataResponse)
def get_grade_reference_data(db: Session = Depends(get_db)) -> GradeReferenceDataResponse:
    """Data referensi mahasiswa & mata kuliah untuk dropdown form web dosen."""
    mhs = list(db.scalars(select(Mahasiswa).order_by(Mahasiswa.nim)).all())
    mks = list(db.scalars(select(MataKuliah).order_by(MataKuliah.kode_mk)).all())
    return GradeReferenceDataResponse(
        mahasiswa=[{"nim": m.nim, "nama": m.nama, "prodi": m.prodi} for m in mhs],
        mata_kuliah=[{"kode_mk": mk.kode_mk, "nama": mk.nama, "sks": mk.sks} for mk in mks],
    )


@router.get("/grades", response_model=list[GradeOut])
def list_grades(
    nim: Optional[str] = Query(default=None),
    semester: Optional[str] = Query(default=None),
    service: GradeService = Depends(get_grade_service),
) -> list[GradeOut]:
    """Menampilkan daftar nilai mahasiswa (dapat difilter per NIM atau semester)."""
    return [_to_grade_out(g) for g in service.list_grades(nim=nim, semester=semester)]


@router.post("/grades", response_model=GradeMutationResponse, status_code=status.HTTP_201_CREATED)
def input_grade(
    payload: GradeInput,
    db: Session = Depends(get_db),
    service: GradeService = Depends(get_grade_service),
) -> GradeMutationResponse:
    """Input nilai mahasiswa oleh dosen (menolak presensi < 75% dan langsung
    mengembalikan IPS & IPK terbaru yang ter-update otomatis).
    """
    grade = service.input_grade(
        nim=payload.nim,
        kode_mk=payload.kode_mk,
        semester=payload.semester,
        nilai_huruf=payload.nilai_huruf,
        presensi_persen=payload.presensi_persen,
        actor=payload.actor,
        reason=payload.reason,
    )
    ips = calculate_ips(db, grade.nim, grade.semester)
    transcript = get_transcript(db, grade.nim)
    return GradeMutationResponse(
        grade=_to_grade_out(grade),
        ips=ips,
        ipk=transcript.ipk,
        predikat=transcript.predikat,
    )


@router.put("/grades/{grade_id}", response_model=GradeMutationResponse)
def update_grade(
    grade_id: int,
    payload: GradeUpdateInput,
    db: Session = Depends(get_db),
    service: GradeService = Depends(get_grade_service),
) -> GradeMutationResponse:
    """Mengubah nilai mahasiswa dengan pencatatan audit trail wajib ke `grade_history`."""
    grade = service.update_grade(
        grade_id=grade_id,
        new_nilai_huruf=payload.nilai_huruf,
        changed_by=payload.changed_by,
        reason=payload.reason,
        presensi_persen=payload.presensi_persen,
    )
    ips = calculate_ips(db, grade.nim, grade.semester)
    transcript = get_transcript(db, grade.nim)
    return GradeMutationResponse(
        grade=_to_grade_out(grade),
        ips=ips,
        ipk=transcript.ipk,
        predikat=transcript.predikat,
    )


@router.get("/grades/history/{nim}", response_model=list[GradeHistoryOut])
def get_grade_history(
    nim: str,
    service: GradeService = Depends(get_grade_service),
) -> list[GradeHistoryOut]:
    """Menampilkan riwayat perubahan nilai (audit trail `grade_history`) per mahasiswa."""
    rows = service.get_grade_history(nim)
    return [
        GradeHistoryOut(
            id=hist.id,
            grade_id=hist.grade_id,
            nim=grade.nim,
            kode_mk=grade.kode_mk,
            semester=grade.semester,
            old_value=hist.old_value,
            new_value=hist.new_value,
            changed_by=hist.changed_by,
            changed_at=hist.changed_at,
            reason=hist.reason,
        )
        for hist, grade in rows
    ]


@router.get("/transcripts/{nim}", response_model=TranscriptResponse)
def get_transcript_json(
    nim: str,
    db: Session = Depends(get_db),
) -> TranscriptResponse:
    """Mengembalikan full academic record (transkrip lengkap) dalam format JSON."""
    t = get_transcript(db, nim)
    return TranscriptResponse(
        nim=t.nim,
        nama=t.nama,
        prodi=t.prodi,
        angkatan=t.angkatan,
        semesters=[
            TranscriptSemesterOut(
                semester=s.semester,
                semester_label=s.semester_label,
                courses=[
                    TranscriptCourseOut(
                        kode_mk=c.kode_mk,
                        nama_mk=c.nama_mk,
                        sks=c.sks,
                        nilai_huruf=c.nilai_huruf,
                        nilai_angka=c.nilai_angka,
                        mutu=c.mutu,
                        is_lulus=c.is_lulus,
                    )
                    for c in s.courses
                ],
                total_sks=s.total_sks,
                total_mutu=s.total_mutu,
                ips=s.ips,
            )
            for s in t.semesters
        ],
        total_sks_lulus=t.total_sks_lulus,
        total_mutu_lulus=t.total_mutu_lulus,
        ipk=t.ipk,
        predikat=t.predikat,
    )


@router.get("/transcripts/{nim}/html", response_class=HTMLResponse)
def get_transcript_html(
    nim: str,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Merender transkrip akademik resmi dalam format HTML + CSS profesional."""
    t = get_transcript(db, nim)
    return HTMLResponse(render_transcript_html(t))


@router.get("/transcripts/{nim}/pdf")
def download_transcript_pdf(
    nim: str,
    db: Session = Depends(get_db),
) -> Response:
    """Menghasilkan dan mengunduh transkrip akademik resmi dalam format PDF (ReportLab)."""
    t = get_transcript(db, nim)
    pdf_bytes = generate_transcript_pdf(t)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="transkrip-{nim}.pdf"'},
    )


@router.get("/transcripts/{nim}/csv")
def download_transcript_csv(
    nim: str,
    db: Session = Depends(get_db),
) -> Response:
    """Menghasilkan dan mengunduh transkrip akademik dalam format CSV."""
    t = get_transcript(db, nim)
    csv_text = export_transcript_to_csv(t)
    return Response(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="transkrip-{nim}.csv"'},
    )
