from collections.abc import Sequence
from datetime import date, datetime, time, timedelta, timezone

from app.models.schedule import Jadwal

# Offset WIB (Asia/Jakarta = UTC+7) tanpa bergantung paket tzdata eksternal di Windows
_WIB_OFFSET = timezone(timedelta(hours=7))


def _first_meeting_date(semester_start: date, hari: int) -> date:
    """Menghitung tanggal pertemuan pertama dari tanggal awal semester dan `hari` (1=Senin..6=Sabtu)."""
    target_weekday = hari - 1  # Python date.weekday(): 0=Senin..6=Minggu
    delta_days = (target_weekday - semester_start.weekday()) % 7
    return semester_start + timedelta(days=delta_days)


def _escape_ics_text(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def export_schedules_to_ics(
    jadwals: Sequence[Jadwal],
    *,
    semester_start: date = date(2025, 9, 1),
    semester_end: date = date(2025, 12, 20),
    tzid: str = "Asia/Jakarta",
    domain: str = "sevima-mini.ac.id",
) -> str:
    """Mengekspor daftar jadwal kuliah ke format iCalendar (RFC 5545, `.ics`).

    Detail penting sesuai spesifikasi:
    - Pemisah baris wajib CRLF (`\\r\\n`).
    - Setiap VEVENT memiliki `UID` stabil (`jadwal-{id}@sevima-mini.ac.id`) dan
      `SEQUENCE` yang naik setiap jadwal berubah agar impor ulang memperbarui
      event lama, bukan membuat duplikat.
    - Karena `DTSTART` memakai zona waktu (`TZID=Asia/Jakarta`), nilai `UNTIL`
      pada `RRULE` ditulis dalam UTC (`YYYYMMDDTHHMMSSZ`).
    """
    now_utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    until_local = datetime.combine(semester_end, time(23, 59, 59), tzinfo=_WIB_OFFSET)
    until_utc = until_local.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    lines: list[str] = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//SIMAK Mini//Modul Jadwal dan Ruang//ID",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-TIMEZONE:{tzid}",
    ]

    for jadwal in jadwals:
        first_date = _first_meeting_date(semester_start, jadwal.hari)
        dtstart = datetime.combine(first_date, jadwal.jam_mulai).strftime("%Y%m%dT%H%M%S")
        dtend = datetime.combine(first_date, jadwal.jam_selesai).strftime("%Y%m%dT%H%M%S")

        kode_mk = jadwal.kelas.kode_mk if jadwal.kelas else f"KELAS-{jadwal.kelas_id}"
        nama_kelas = jadwal.kelas.nama_kelas if jadwal.kelas else ""
        nama_mk = (
            jadwal.kelas.mata_kuliah.nama
            if jadwal.kelas and jadwal.kelas.mata_kuliah
            else kode_mk
        )
        dosen_nama = jadwal.dosen.nama if jadwal.dosen else f"Dosen #{jadwal.dosen_id}"

        summary = _escape_ics_text(f"{kode_mk} {nama_mk} ({nama_kelas})".strip())
        location = _escape_ics_text(f"Ruang {jadwal.ruangan_kode}")
        description = _escape_ics_text(
            f"Dosen: {dosen_nama}\nKelas: {kode_mk}-{nama_kelas}\nRuangan: {jadwal.ruangan_kode}"
        )
        sequence = getattr(jadwal, "sequence", 0) or 0

        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:jadwal-{jadwal.id}@{domain}",
                f"DTSTAMP:{now_utc}",
                f"SEQUENCE:{sequence}",
                f"SUMMARY:{summary}",
                f"LOCATION:{location}",
                f"DESCRIPTION:{description}",
                f"DTSTART;TZID={tzid}:{dtstart}",
                f"DTEND;TZID={tzid}:{dtend}",
                f"RRULE:FREQ=WEEKLY;UNTIL={until_utc}",
                "END:VEVENT",
            ]
        )

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
