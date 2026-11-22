from datetime import date
from io import BytesIO

from reportlab.graphics.shapes import Circle, Drawing, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.services.gpa_calculator import TranscriptData

_NAVY = colors.HexColor("#0f172a")
_ACCENT = colors.HexColor("#1d4ed8")
_GOLD = colors.HexColor("#b45309")
_SLATE = colors.HexColor("#475569")
_LIGHT_BG = colors.HexColor("#f1f5f9")
_BORDER = colors.HexColor("#cbd5e1")


def _build_university_logo() -> Drawing:
    """Logo vektor universitas sederhana memakai ReportLab Drawing (tanpa file gambar eksternal)."""
    d = Drawing(44, 44)
    d.add(Circle(22, 22, 20, fillColor=_NAVY, strokeColor=_GOLD, strokeWidth=2))
    d.add(Circle(22, 22, 16, fillColor=None, strokeColor=colors.white, strokeWidth=0.8))
    d.add(Rect(14, 15, 16, 12, fillColor=_GOLD, strokeColor=colors.white, strokeWidth=0.6))
    d.add(String(22, 18.5, "SM", fontName="Helvetica-Bold", fontSize=10, fillColor=colors.white, textAnchor="middle"))
    return d


def generate_transcript_pdf(
    transcript: TranscriptData,
    *,
    university_name: str = "UNIVERSITAS SIMAK MINI NUSANTARA",
    faculty_name: str = "FAKULTAS TEKNOLOGI INFORMASI & ILMU KOMPUTER",
    dean_name: str = "Prof. Dr. Ir. Hendra Kusuma, M.T.",
    dean_nip: str = "NIP. 19720415 199803 1 002",
    issue_date: date | None = None,
) -> bytes:
    """Menghasilkan dokumen PDF resmi 'TRANSKRIP AKADEMIK' memakai ReportLab.

    Layout sesuai Step 2 spesifikasi:
    - Header : Logo universitas, nama universitas, judul 'TRANSKRIP AKADEMIK'
    - Biodata: NIM, Nama, Program Studi, Angkatan
    - Per semester: tabel [Kode MK | Nama MK | SKS | Nilai | Mutu] + subtotal IPS
    - Footer : Total SKS, IPK, Predikat Kelulusan, dan TTD Dekan
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"Transkrip Akademik - {transcript.nim}",
        author=university_name,
    )

    styles = getSampleStyleSheet()
    style_uni = ParagraphStyle(
        "UniTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=16,
        textColor=_NAVY,
        alignment=TA_CENTER,
    )
    style_fac = ParagraphStyle(
        "FacTitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=_SLATE,
        alignment=TA_CENTER,
    )
    style_doc_title = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        textColor=_ACCENT,
        alignment=TA_CENTER,
        spaceBefore=4,
        spaceAfter=2,
    )
    style_section = ParagraphStyle(
        "SectionTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9.5,
        leading=13,
        textColor=_NAVY,
        spaceBefore=8,
        spaceAfter=4,
    )
    style_cell = ParagraphStyle(
        "CellText",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        textColor=_NAVY,
    )
    style_muted = ParagraphStyle(
        "MutedText",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=8.5,
        leading=11,
        textColor=_SLATE,
    )
    style_sign = ParagraphStyle(
        "SignText",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=_NAVY,
        alignment=TA_LEFT,
    )

    story = []

    # 1. HEADER: Logo Universitas + Judul 'TRANSKRIP AKADEMIK'
    header_table = Table(
        [
            [
                _build_university_logo(),
                [
                    Paragraph(university_name, style_uni),
                    Paragraph(faculty_name, style_fac),
                    Paragraph("TRANSKRIP AKADEMIK", style_doc_title),
                ],
                "",
            ]
        ],
        colWidths=[22 * mm, 130 * mm, 22 * mm],
    )
    header_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (0, 0), "LEFT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    story.append(header_table)
    story.append(Spacer(1, 3 * mm))
    story.append(HRFlowable(width="100%", thickness=1.8, color=_NAVY))
    story.append(HRFlowable(width="100%", thickness=0.6, color=_GOLD, spaceBefore=1.5, spaceAfter=6))

    # 2. BIODATA MAHASISWA
    bio_data = [
        ["NIM", f": {transcript.nim}", "Program Studi", f": {transcript.prodi}"],
        ["Nama Mahasiswa", f": {transcript.nama}", "Angkatan", f": {transcript.angkatan}"],
    ]
    bio_table = Table(bio_data, colWidths=[30 * mm, 62 * mm, 28 * mm, 54 * mm])
    bio_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("FONTNAME", (3, 0), (3, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TEXTCOLOR", (0, 0), (-1, -1), _NAVY),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BACKGROUND", (0, 0), (-1, -1), _LIGHT_BG),
                ("BOX", (0, 0), (-1, -1), 0.6, _BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(bio_table)
    story.append(Spacer(1, 4 * mm))

    # 3. TABEL PER SEMESTER: [Kode MK | Nama MK | SKS | Nilai | Mutu]
    if not transcript.semesters:
        story.append(
            Paragraph(
                "Belum ada catatan nilai mata kuliah yang tercatat pada transkrip ini.",
                style_muted,
            )
        )
    else:
        for sem in transcript.semesters:
            story.append(Paragraph(sem.semester_label, style_section))
            rows = [["Kode MK", "Nama Mata Kuliah", "SKS", "Nilai", "Mutu"]]
            for item in sem.courses:
                rows.append(
                    [
                        item.kode_mk,
                        Paragraph(item.nama_mk, style_cell),
                        str(item.sks),
                        f"{item.nilai_huruf} ({item.nilai_angka:.2f})",
                        f"{item.mutu:.2f}",
                    ]
                )
            rows.append(
                [
                    "",
                    f"Subtotal Semester — IPS: {sem.ips:.2f}",
                    str(sem.total_sks),
                    "",
                    f"{sem.total_mutu:.2f}",
                ]
            )

            sem_table = Table(
                rows,
                colWidths=[24 * mm, 82 * mm, 16 * mm, 28 * mm, 24 * mm],
                repeatRows=1,
            )
            sem_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), _NAVY),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                        ("ALIGN", (0, 0), (0, -1), "CENTER"),
                        ("ALIGN", (2, 0), (-1, -1), "CENTER"),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("GRID", (0, 0), (-1, -1), 0.4, _BORDER),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#f8fafc")]),
                        ("BACKGROUND", (0, -1), (-1, -1), _LIGHT_BG),
                        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ]
                )
            )
            story.append(sem_table)
            story.append(Spacer(1, 3 * mm))

    story.append(Spacer(1, 4 * mm))

    # 4. FOOTER: Summary (Total SKS, IPK, Predikat) + TTD Dekan
    printed = issue_date or date.today()
    summary_rows = [
        ["RINGKASAN AKADEMIK", ""],
        ["Total SKS Lulus", f"{transcript.total_sks_lulus} SKS"],
        ["Total Angka Mutu", f"{transcript.total_mutu_lulus:.2f}"],
        ["Indeks Prestasi Kumulatif (IPK)", f"{transcript.ipk:.2f}"],
        ["Predikat Kelulusan", transcript.predikat],
    ]
    summary_table = Table(summary_rows, colWidths=[56 * mm, 44 * mm])
    summary_table.setStyle(
        TableStyle(
            [
                ("SPAN", (0, 0), (1, 0)),
                ("BACKGROUND", (0, 0), (1, 0), _NAVY),
                ("TEXTCOLOR", (0, 0), (1, 0), colors.white),
                ("FONTNAME", (0, 0), (1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("GRID", (0, 0), (-1, -1), 0.5, _BORDER),
                ("BACKGROUND", (0, 3), (1, 4), colors.HexColor("#eff6ff")),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )

    sign_block = [
        Paragraph(f"Ditetapkan pada: {printed.strftime('%d %B %Y')}", style_sign),
        Paragraph("Dekan Fakultas Teknologi Informasi,", style_sign),
        Spacer(1, 14 * mm),
        Paragraph(f"<b>{dean_name}</b>", style_sign),
        Paragraph(dean_nip, style_muted),
    ]

    footer_table = Table(
        [[summary_table, sign_block]],
        colWidths=[106 * mm, 68 * mm],
    )
    footer_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    story.append(footer_table)

    doc.build(story)
    return buffer.getvalue()
