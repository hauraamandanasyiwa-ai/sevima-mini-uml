import csv
from datetime import date
from html import escape
from io import StringIO

from app.services.gpa_calculator import TranscriptData


def render_transcript_html(
    transcript: TranscriptData,
    *,
    university_name: str = "UNIVERSITAS SIMAK MINI NUSANTARA",
    faculty_name: str = "FAKULTAS TEKNOLOGI INFORMASI & ILMU KOMPUTER",
    dean_name: str = "Prof. Dr. Ir. Hendra Kusuma, M.T.",
    dean_nip: str = "NIP. 19720415 199803 1 002",
    issue_date: date | None = None,
) -> str:
    """Merender template HTML dinamis dengan CSS profesional mirip ijazah resmi
    (Step 2 PDF Generation & Print-Ready Transcript).
    """
    printed = (issue_date or date.today()).strftime("%d %B %Y")

    semester_sections = []
    for sem in transcript.semesters:
        rows_html = []
        for c in sem.courses:
            status_badge = (
                '<span class="pass">Lulus</span>'
                if c.is_lulus
                else '<span class="fail">Tidak Lulus</span>'
            )
            rows_html.append(
                f"<tr>"
                f"<td class='center'>{escape(c.kode_mk)}</td>"
                f"<td>{escape(c.nama_mk)} {status_badge}</td>"
                f"<td class='center'>{c.sks}</td>"
                f"<td class='center'><strong>{escape(c.nilai_huruf)}</strong> ({c.nilai_angka:.2f})</td>"
                f"<td class='center'>{c.mutu:.2f}</td>"
                f"</tr>"
            )
        semester_sections.append(
            f"""
            <section class="semester-block">
              <h3>{escape(sem.semester_label)}</h3>
              <table>
                <thead>
                  <tr>
                    <th style="width:14%">Kode MK</th>
                    <th>Nama Mata Kuliah</th>
                    <th style="width:10%">SKS</th>
                    <th style="width:18%">Nilai</th>
                    <th style="width:14%">Mutu</th>
                  </tr>
                </thead>
                <tbody>
                  {''.join(rows_html)}
                </tbody>
                <tfoot>
                  <tr>
                    <td colspan="2" class="right"><strong>Subtotal Semester &bull; IPS: {sem.ips:.2f}</strong></td>
                    <td class="center"><strong>{sem.total_sks}</strong></td>
                    <td></td>
                    <td class="center"><strong>{sem.total_mutu:.2f}</strong></td>
                  </tr>
                </tfoot>
              </table>
            </section>
            """
        )

    body_semesters = (
        "".join(semester_sections)
        if semester_sections
        else '<p class="empty">Belum ada catatan nilai yang tersimpan untuk mahasiswa ini.</p>'
    )

    return f"""<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Transkrip Akademik - {escape(transcript.nim)}</title>
  <style>
    @page {{ size: A4; margin: 14mm; }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      padding: 24px;
      background: #e2e8f0;
      font-family: "Georgia", "Times New Roman", serif;
      color: #0f172a;
    }}
    .sheet {{
      max-width: 820px;
      margin: 0 auto;
      background: #ffffff;
      border: 6px double #0f172a;
      outline: 2px solid #b45309;
      outline-offset: -12px;
      padding: 32px 36px;
      box-shadow: 0 12px 30px rgba(15, 23, 42, 0.14);
    }}
    .toolbar {{
      max-width: 820px;
      margin: 0 auto 14px;
      display: flex;
      justify-content: flex-end;
      gap: 10px;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    .btn {{
      padding: 8px 14px;
      border-radius: 6px;
      text-decoration: none;
      font-size: 0.85rem;
      font-weight: 600;
      cursor: pointer;
      border: 1px solid #cbd5e1;
      background: #fff;
      color: #0f172a;
    }}
    .btn-primary {{ background: #1d4ed8; color: #fff; border-color: #1d4ed8; }}
    @media print {{ .toolbar {{ display: none; }} body {{ background: #fff; padding: 0; }} .sheet {{ box-shadow: none; }} }}
    .header {{
      display: flex;
      align-items: center;
      gap: 18px;
      border-bottom: 3px double #0f172a;
      padding-bottom: 14px;
      margin-bottom: 18px;
    }}
    .emblem {{
      width: 64px;
      height: 64px;
      border-radius: 50%;
      background: #0f172a;
      border: 3px solid #b45309;
      color: #fff;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 700;
      font-size: 1.25rem;
      flex-shrink: 0;
    }}
    .header-text {{ flex: 1; text-align: center; padding-right: 64px; }}
    .header-text h1 {{ margin: 0; font-size: 1.25rem; letter-spacing: 0.6px; }}
    .header-text p {{ margin: 2px 0; font-size: 0.85rem; color: #475569; }}
    .header-text h2 {{ margin: 8px 0 0; font-size: 1.15rem; color: #1d4ed8; letter-spacing: 2px; }}
    .biodata {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 6px 24px;
      background: #f8fafc;
      border: 1px solid #cbd5e1;
      padding: 12px 16px;
      margin-bottom: 18px;
      font-size: 0.92rem;
    }}
    .biodata div strong {{ display: inline-block; width: 125px; }}
    .semester-block {{ margin-bottom: 16px; }}
    .semester-block h3 {{
      margin: 0 0 6px;
      font-size: 0.96rem;
      color: #0f172a;
      border-left: 4px solid #b45309;
      padding-left: 8px;
    }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.88rem; }}
    th, td {{ border: 1px solid #cbd5e1; padding: 6px 8px; }}
    thead th {{ background: #0f172a; color: #fff; text-align: center; }}
    tfoot td {{ background: #f1f5f9; }}
    .center {{ text-align: center; }}
    .right {{ text-align: right; }}
    .pass {{ font-size: 0.72rem; color: #15803d; margin-left: 6px; font-family: sans-serif; }}
    .fail {{ font-size: 0.72rem; color: #b91c1c; margin-left: 6px; font-family: sans-serif; }}
    .footer {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 24px;
      margin-top: 22px;
      padding-top: 14px;
      border-top: 1px solid #cbd5e1;
    }}
    .summary {{
      width: 55%;
      border: 1px solid #0f172a;
      padding: 12px 14px;
      background: #eff6ff;
      font-size: 0.92rem;
    }}
    .summary div {{ display: flex; justify-content: space-between; margin: 4px 0; }}
    .signature {{ width: 40%; text-align: left; font-size: 0.9rem; }}
    .signature .space {{ height: 58px; }}
    .empty {{ font-style: italic; color: #64748b; text-align: center; padding: 18px 0; }}
  </style>
</head>
<body>
  <div class="toolbar">
    <a class="btn" href="/grades-portal">Kembali ke Portal Nilai</a>
    <a class="btn btn-primary" href="/transcripts/{escape(transcript.nim)}/pdf">Download PDF Resmi</a>
    <button class="btn" onclick="window.print()">Cetak Halaman</button>
  </div>
  <article class="sheet">
    <header class="header">
      <div class="emblem">SM</div>
      <div class="header-text">
        <h1>{escape(university_name)}</h1>
        <p>{escape(faculty_name)}</p>
        <h2>TRANSKRIP AKADEMIK</h2>
      </div>
    </header>

    <section class="biodata">
      <div><strong>NIM</strong>: {escape(transcript.nim)}</div>
      <div><strong>Program Studi</strong>: {escape(transcript.prodi)}</div>
      <div><strong>Nama</strong>: {escape(transcript.nama)}</div>
      <div><strong>Angkatan</strong>: {escape(transcript.angkatan)}</div>
    </section>

    {body_semesters}

    <footer class="footer">
      <div class="summary">
        <div><span>Total SKS Lulus</span><strong>{transcript.total_sks_lulus} SKS</strong></div>
        <div><span>Total Angka Mutu</span><strong>{transcript.total_mutu_lulus:.2f}</strong></div>
        <div><span>Indeks Prestasi Kumulatif (IPK)</span><strong>{transcript.ipk:.2f}</strong></div>
        <div><span>Predikat Kelulusan</span><strong>{escape(transcript.predikat)}</strong></div>
      </div>
      <div class="signature">
        <div>Ditetapkan pada: {escape(printed)}</div>
        <div>Dekan Fakultas Teknologi Informasi,</div>
        <div class="space"></div>
        <div><strong>{escape(dean_name)}</strong></div>
        <div style="color:#475569;font-size:0.82rem;">{escape(dean_nip)}</div>
      </div>
    </footer>
  </article>
</body>
</html>
"""


def export_transcript_to_csv(transcript: TranscriptData) -> str:
    """Mengekspor ringkasan transkrip akademik ke format CSV."""
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["NIM", "Nama", "Prodi", "Angkatan", "Semester", "Kode MK", "Nama MK", "SKS", "Nilai Huruf", "Nilai Angka", "Mutu", "Status"])
    for sem in transcript.semesters:
        for c in sem.courses:
            writer.writerow(
                [
                    transcript.nim,
                    transcript.nama,
                    transcript.prodi,
                    transcript.angkatan,
                    sem.semester,
                    c.kode_mk,
                    c.nama_mk,
                    c.sks,
                    c.nilai_huruf,
                    f"{c.nilai_angka:.2f}",
                    f"{c.mutu:.2f}",
                    "Lulus" if c.is_lulus else "Tidak Lulus",
                ]
            )
    writer.writerow([])
    writer.writerow(["SUMMARY", f"Total SKS Lulus={transcript.total_sks_lulus}", f"IPK={transcript.ipk:.2f}", f"Predikat={transcript.predikat}"])
    return output.getvalue()
