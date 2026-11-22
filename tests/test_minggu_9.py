from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.exceptions import InsufficientAttendanceError, InvalidGradeValueError
from app.models.krs import MataKuliah
from app.services.gpa_calculator import (
    GradeRecord,
    calculate_ipk,
    calculate_ipk_from_records,
    calculate_ips,
    get_transcript,
    konversi_huruf_ke_angka,
    tentukan_predikat,
)
from app.services.grade_service import GradeService
from app.services.transcript_html import export_transcript_to_csv, render_transcript_html
from app.services.transcript_pdf import generate_transcript_pdf


def _rec(kode: str, sks: int, sem: str, huruf: str) -> GradeRecord:
    return GradeRecord(
        kode_mk=kode,
        nama_mk=f"MK {kode}",
        sks=sks,
        semester=sem,
        nilai_huruf=huruf,
        nilai_angka=konversi_huruf_ke_angka(huruf),
    )


# ============================================================================
# 12 KASUS UNIT TEST PERHITUNGAN IPK (Kriteria Sukses: 10+ kasus!)
# ============================================================================


@pytest.mark.parametrize(
    ("case_name", "records", "expected_ipk", "expected_sks", "expected_predikat"),
    [
        # 1. Mahasiswa dengan nilai sempurna (semua A)
        (
            "semua_a_sempurna",
            [_rec("IF101", 3, "20241", "A"), _rec("MA101", 3, "20241", "A"), _rec("IF202", 4, "20242", "A")],
            Decimal("4.00"),
            10,
            "Cum Laude",
        ),
        # 2. Mahasiswa semester awal (belum ada nilai -> return 0.00)
        (
            "semester_awal_kosong",
            [],
            Decimal("0.00"),
            0,
            "Belum Ada Nilai",
        ),
        # 3. MK diulang (C -> A): ambil nilai tertinggi A, SKS hanya dihitung sekali!
        (
            "mk_diulang_naik_c_ke_a",
            [_rec("IF101", 3, "20241", "C"), _rec("IF101", 3, "20242", "A"), _rec("MA101", 3, "20241", "B")],
            Decimal("3.50"),
            6,
            "Cum Laude",
        ),
        # 4. MK diulang tapi percobaan kedua lebih rendah (A -> C): tetap ambil tertinggi A!
        (
            "mk_diulang_turun_tetap_ambil_tertinggi",
            [_rec("IF101", 3, "20241", "A"), _rec("IF101", 3, "20242", "C")],
            Decimal("4.00"),
            3,
            "Cum Laude",
        ),
        # 5. MK tidak lulus (E) diabaikan dari IPK
        (
            "nilai_e_diabaikan",
            [_rec("IF101", 3, "20241", "B"), _rec("MA101", 3, "20241", "E")],
            Decimal("3.00"),
            3,
            "Sangat Memuaskan",
        ),
        # 6. Semua MK tidak lulus (semua E) -> 0.00
        (
            "semua_e_tidak_lulus",
            [_rec("IF101", 3, "20241", "E"), _rec("MA101", 3, "20241", "E")],
            Decimal("0.00"),
            0,
            "Belum Ada Nilai",
        ),
        # 7. MK diulang dari E (tidak lulus) -> B (lulus)
        (
            "mk_diulang_e_ke_b",
            [_rec("IF101", 3, "20241", "E"), _rec("IF101", 3, "20242", "B")],
            Decimal("3.00"),
            3,
            "Sangat Memuaskan",
        ),
        # 8. Nilai batas lulus D (1.00) tetap dihitung
        (
            "batas_lulus_nilai_d",
            [_rec("IF101", 3, "20241", "D"), _rec("MA101", 3, "20241", "B")],
            Decimal("2.00"),
            6,
            "Cukup",
        ),
        # 9. Bobot SKS berbeda (2 SKS A=4.0 + 4 SKS B=3.0 => (8+12)/6 = 3.33)
        (
            "bobot_sks_berbeda",
            [_rec("MK2", 2, "20241", "A"), _rec("MK4", 4, "20241", "B")],
            Decimal("3.33"),
            6,
            "Sangat Memuaskan",
        ),
        # 10. MK diulang 3 kali (E -> D -> B+) -> ambil B+ (3.30)
        (
            "mk_diulang_3_kali",
            [_rec("IF101", 3, "20241", "E"), _rec("IF101", 3, "20242", "D"), _rec("IF101", 3, "20251", "B+")],
            Decimal("3.30"),
            3,
            "Sangat Memuaskan",
        ),
        # 11. Predikat Memuaskan (2.75 <= IPK < 3.00): B- (2.70) & B (3.00) -> 2.85
        (
            "predikat_memuaskan",
            [_rec("IF101", 3, "20241", "B-"), _rec("MA101", 3, "20241", "B")],
            Decimal("2.85"),
            6,
            "Memuaskan",
        ),
        # 12. Pembulatan ROUND_HALF_UP & batas bawah Cum Laude (3.49 vs 3.50):
        #     3 SKS A (4.0) + 3 SKS B (3.0) + 3 SKS A- (3.7) => (12+9+11.1)/9 = 3.5666 -> 3.57
        (
            "pembulatan_round_half_up",
            [_rec("IF101", 3, "20241", "A"), _rec("MA101", 3, "20241", "B"), _rec("IF202", 3, "20242", "A-")],
            Decimal("3.57"),
            9,
            "Cum Laude",
        ),
    ],
)
def test_ipk_calculation_12_cases(
    case_name: str,
    records: list[GradeRecord],
    expected_ipk: Decimal,
    expected_sks: int,
    expected_predikat: str,
) -> None:
    ipk, total_sks, _ = calculate_ipk_from_records(records)
    assert ipk == expected_ipk, f"Gagal pada kasus {case_name}"
    assert total_sks == expected_sks
    assert tentukan_predikat(ipk, total_sks) == expected_predikat


# ============================================================================
# BUSINESS RULES: Presensi < 75% ditolak, >= 75% diterima, IPS/IPK DB
# ============================================================================


def test_attendance_below_75_percent_is_rejected_and_75_is_accepted(db_session: Session) -> None:
    service = GradeService(db_session)

    # Presensi 74.99% -> ditolak
    with pytest.raises(InsufficientAttendanceError, match="75%"):
        service.input_grade(
            nim="20240001",
            kode_mk="IF101",
            semester="20251",
            nilai_huruf="A",
            presensi_persen=Decimal("74.99"),
            actor="Dr. Daniel",
        )

    # Presensi tepat 75.00% -> diterima
    grade = service.input_grade(
        nim="20240001",
        kode_mk="IF101",
        semester="20251",
        nilai_huruf="A",
        presensi_persen=Decimal("75.00"),
        actor="Dr. Daniel",
    )
    assert grade.nilai_huruf == "A"
    assert grade.nilai_angka == Decimal("4.00")


def test_ips_ipk_and_repeat_course_from_database(db_session: Session) -> None:
    service = GradeService(db_session)

    # Mahasiswa semester awal belum ada nilai -> 0.00
    assert calculate_ipk(db_session, "20240002") == Decimal("0.00")
    assert calculate_ips(db_session, "20240002", "20251") == Decimal("0.00")

    # Semester 20242: IF101 = C (2.0), MA101 = B (3.0) -> IPS 20242 = 2.50
    service.input_grade(
        nim="20240001", kode_mk="IF101", semester="20242",
        nilai_huruf="C", presensi_persen=Decimal("85"), actor="Dr. Daniel",
    )
    service.input_grade(
        nim="20240001", kode_mk="MA101", semester="20242",
        nilai_huruf="B", presensi_persen=Decimal("90"), actor="Prof. Rina",
    )
    assert calculate_ips(db_session, "20240001", "20242") == Decimal("2.50")

    # Semester 20251: mengulang IF101 -> A (4.0) -> IPK ambil A (4.0) + MA101 B (3.0) = 3.50
    service.input_grade(
        nim="20240001", kode_mk="IF101", semester="20251",
        nilai_huruf="A", presensi_persen=Decimal("95"), actor="Dr. Daniel",
    )
    assert calculate_ips(db_session, "20240001", "20251") == Decimal("4.00")
    assert calculate_ipk(db_session, "20240001") == Decimal("3.50")


# ============================================================================
# AUDIT TRAIL: Edit nilai wajib reason & menulis baris ke `grade_history`
# ============================================================================


def test_update_grade_requires_reason_and_writes_audit_trail(db_session: Session) -> None:
    service = GradeService(db_session)
    grade = service.input_grade(
        nim="20240001",
        kode_mk="IF202",
        semester="20251",
        nilai_huruf="B",
        presensi_persen=Decimal("88"),
        actor="Dr. Daniel",
    )

    # Edit tanpa alasan -> ditolak
    with pytest.raises(InvalidGradeValueError, match="Alasan"):
        service.update_grade(
            grade_id=grade.id,
            new_nilai_huruf="A",
            changed_by="Dr. Daniel",
            reason="   ",
        )

    # Edit dengan alasan valid -> nilai berubah + 1 baris grade_history tercatat
    updated = service.update_grade(
        grade_id=grade.id,
        new_nilai_huruf="A",
        changed_by="Dr. Daniel",
        reason="Perbaikan nilai setelah remidi UAS",
    )
    assert updated.nilai_huruf == "A"
    assert updated.nilai_angka == Decimal("4.00")

    history = service.get_grade_history("20240001")
    assert len(history) == 1
    hist_row, grade_row = history[0]
    assert grade_row.kode_mk == "IF202"
    assert hist_row.old_value == "B"
    assert hist_row.new_value == "A"
    assert hist_row.changed_by == "Dr. Daniel"
    assert "remidi" in hist_row.reason


# ============================================================================
# PDF GENERATOR (ReportLab), HTML TEMPLATE, CSV, & END-TO-END API
# ============================================================================


def test_transcript_pdf_html_csv_and_api_end_to_end(
    api_client: TestClient,
    db_session: Session,
) -> None:
    # 1. Input nilai dengan presensi < 75% -> 400 Bad Request
    r_low = api_client.post(
        "/grades",
        json={
            "nim": "20240001",
            "kode_mk": "IF101",
            "semester": "20251",
            "nilai_huruf": "A",
            "presensi_persen": 60,
            "actor": "Dr. Daniel",
        },
    )
    assert r_low.status_code == 400

    # 2. Input 2 nilai sah -> IPK langsung ter-update otomatis di respons!
    r1 = api_client.post(
        "/grades",
        json={
            "nim": "20240001",
            "kode_mk": "IF101",
            "semester": "20251",
            "nilai_huruf": "B",
            "presensi_persen": 90,
            "actor": "Dr. Daniel",
        },
    )
    assert r1.status_code == 201
    assert Decimal(str(r1.json()["ipk"])) == Decimal("3.00")
    grade_id = r1.json()["grade"]["id"]

    # 3. Edit nilai B -> A dengan alasan -> IPK naik jadi 4.00 (Cum Laude) & tercatat di history
    r_edit = api_client.put(
        f"/grades/{grade_id}",
        json={
            "nilai_huruf": "A",
            "changed_by": "Dr. Daniel",
            "reason": "Koreksi bobot proyek akhir",
        },
    )
    assert r_edit.status_code == 200
    assert Decimal(str(r_edit.json()["ipk"])) == Decimal("4.00")
    assert r_edit.json()["predikat"] == "Cum Laude"

    r_hist = api_client.get("/grades/history/20240001")
    assert r_hist.status_code == 200
    assert len(r_hist.json()) == 1
    assert r_hist.json()[0]["old_value"] == "B"
    assert r_hist.json()[0]["new_value"] == "A"

    # 4. Download Transkrip PDF resmi (ReportLab) -> valid %PDF- bytes
    r_pdf = api_client.get("/transcripts/20240001/pdf")
    assert r_pdf.status_code == 200
    assert r_pdf.headers["content-type"] == "application/pdf"
    assert r_pdf.content.startswith(b"%PDF-")
    assert len(r_pdf.content) > 1500

    # 5. Template HTML profesional & CSV & Portal Web Dosen
    r_html = api_client.get("/transcripts/20240001/html")
    assert r_html.status_code == 200
    assert "TRANSKRIP AKADEMIK" in r_html.text
    assert "20240001" in r_html.text
    assert "Cum Laude" in r_html.text

    r_csv = api_client.get("/transcripts/20240001/csv")
    assert r_csv.status_code == 200
    assert "text/csv" in r_csv.headers["content-type"]
    assert "IF101" in r_csv.text

    r_portal = api_client.get("/grades-portal")
    assert r_portal.status_code == 200
    assert "Portal Input Nilai" in r_portal.text

    # Verifikasi pemanggilan langsung fungsi generator tanpa HTTP
    transcript = get_transcript(db_session, "20240001")
    assert generate_transcript_pdf(transcript).startswith(b"%PDF-")
    assert "TRANSKRIP AKADEMIK" in render_transcript_html(transcript)
    assert "Cum Laude" in export_transcript_to_csv(transcript)
