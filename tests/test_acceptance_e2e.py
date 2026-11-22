from datetime import time
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.krs import KRS, KRSDetail, KRSStatus
from app.models.schedule import Dosen, Jadwal, Kelas


def test_end_to_end_academic_journey_krs_schedule_grades_transcript_pdf(
    api_client: TestClient,
    db_session: Session,
) -> None:
    """Acceptance Test End-to-End (Minggu 5-10) dari ujung ke ujung:
    1. Mahasiswa (20240001) mengisi KRS -> Submit -> Approve oleh Dosen PA.
    2. Admin mengubah jadwal kelas yang diambil -> KRS otomatis kembali ke `revision`
       (aktor `system`) & outbox + notifikasi 3 kanal terkirim setelah commit.
    3. Dosen mencoba input nilai dengan presensi 60% -> ditolak (400).
    4. Dosen input nilai sah pada 2 semester (termasuk MK diulang: C -> A) ->
       IPS & IPK ter-update otomatis mengambil nilai tertinggi.
    5. Dosen mengedit nilai dengan alasan -> tercatat di `grade_history`.
    6. Sistem men-generate & mengunduh Transkrip PDF (ReportLab), HTML resmi,
       CSV, serta Ekspor Kalender (.ics).
    """
    admin_headers = {"X-Role": "admin_akademik"}

    # --- TAHAP 1: KRS APPROVED + Jadwal kelas aktif ---
    k_bd_a = db_session.scalars(
        select(Kelas).where(Kelas.kode_mk == "IF202", Kelas.nama_kelas == "A")
    ).one()
    d1 = db_session.scalars(select(Dosen).where(Dosen.nidn == "0101018501")).one()

    krs = KRS(
        nim="20240001",
        semester="20251",
        status=KRSStatus.APPROVED,
        dosen_pa_id="PA001",
    )
    db_session.add(krs)
    db_session.flush()
    db_session.add(KRSDetail(krs_id=krs.id, kode_mk="IF202", kelas_id=k_bd_a.id))
    db_session.commit()

    r_create = api_client.post(
        "/schedules",
        json={
            "kelas_id": k_bd_a.id,
            "ruangan_kode": "A101",
            "dosen_id": d1.id,
            "hari": 1,
            "jam_mulai": "08:00:00",
            "jam_selesai": "09:40:00",
        },
    )
    assert r_create.status_code == 201
    jadwal_id = r_create.json()["id"]

    # --- TAHAP 2: Admin pindahkan jadwal -> KRS otomatis kembali ke REVISION ---
    r_move = api_client.put(
        f"/schedules/{jadwal_id}",
        json={
            "kelas_id": k_bd_a.id,
            "ruangan_kode": "A101",
            "dosen_id": d1.id,
            "hari": 3,
            "jam_mulai": "13:00:00",
            "jam_selesai": "14:40:00",
        },
    )
    assert r_move.status_code == 200
    assert r_move.json()["sequence"] == 1

    db_session.refresh(krs)
    assert krs.status == KRSStatus.REVISION

    r_logs = api_client.get("/admin/notifications/logs", headers=admin_headers)
    assert r_logs.status_code == 200
    assert r_logs.json()["total_logs"] >= 3  # email, sms, push

    # --- TAHAP 3: Business Rule Presensi < 75% ditolak ---
    r_reject = api_client.post(
        "/grades",
        json={
            "nim": "20240001",
            "kode_mk": "IF202",
            "semester": "20251",
            "nilai_huruf": "A",
            "presensi_persen": 65,
            "actor": "Dr. Daniel Pratama",
        },
    )
    assert r_reject.status_code == 400

    # --- TAHAP 4: Input Nilai Multi-Semester + MK Diulang (IF101: C -> A) ---
    r_g1 = api_client.post(
        "/grades",
        json={
            "nim": "20240001",
            "kode_mk": "IF101",
            "semester": "20242",
            "nilai_huruf": "C",
            "presensi_persen": 85,
            "actor": "Dr. Daniel Pratama",
        },
    )
    assert r_g1.status_code == 201
    assert Decimal(str(r_g1.json()["ipk"])) == Decimal("2.00")

    r_g2 = api_client.post(
        "/grades",
        json={
            "nim": "20240001",
            "kode_mk": "IF101",
            "semester": "20251",
            "nilai_huruf": "A",
            "presensi_persen": 95,
            "actor": "Dr. Daniel Pratama",
        },
    )
    assert r_g2.status_code == 201
    # MK IF101 diulang: C (2.0) -> A (4.0), IPK wajib ambil tertinggi = 4.00
    assert Decimal(str(r_g2.json()["ipk"])) == Decimal("4.00")

    r_g3 = api_client.post(
        "/grades",
        json={
            "nim": "20240001",
            "kode_mk": "IF202",
            "semester": "20251",
            "nilai_huruf": "B",
            "presensi_persen": 90,
            "actor": "Dr. Daniel Pratama",
        },
    )
    assert r_g3.status_code == 201
    assert Decimal(str(r_g3.json()["ipk"])) == Decimal("3.50")
    assert r_g3.json()["predikat"] == "Cum Laude"
    grade_bd_id = r_g3.json()["grade"]["id"]

    # --- TAHAP 5: Edit Nilai + Verifikasi Audit Trail (`grade_history`) ---
    r_upd = api_client.put(
        f"/grades/{grade_bd_id}",
        json={
            "nilai_huruf": "A-",
            "changed_by": "Dr. Daniel Pratama",
            "reason": "Koreksi nilai proyek akhir",
        },
    )
    assert r_upd.status_code == 200
    assert Decimal(str(r_upd.json()["ipk"])) == Decimal("3.85")

    r_hist = api_client.get("/grades/history/20240001")
    assert r_hist.status_code == 200
    hist = r_hist.json()
    assert len(hist) == 1
    assert hist[0]["old_value"] == "B"
    assert hist[0]["new_value"] == "A-"
    assert hist[0]["changed_by"] == "Dr. Daniel Pratama"

    # --- TAHAP 6: Verifikasi Transkrip JSON, HTML, PDF, CSV, dan Kalender .ics ---
    r_tr = api_client.get("/transcripts/20240001")
    assert r_tr.status_code == 200
    tr = r_tr.json()
    assert tr["total_sks_lulus"] == 6
    assert Decimal(str(tr["ipk"])) == Decimal("3.85")
    assert tr["predikat"] == "Cum Laude"
    assert len(tr["semesters"]) == 2

    r_pdf = api_client.get("/transcripts/20240001/pdf")
    assert r_pdf.status_code == 200
    assert r_pdf.content.startswith(b"%PDF-")

    r_html = api_client.get("/transcripts/20240001/html")
    assert r_html.status_code == 200
    assert "TRANSKRIP AKADEMIK" in r_html.text
    assert "3.85" in r_html.text

    r_csv = api_client.get("/transcripts/20240001/csv")
    assert r_csv.status_code == 200
    assert "IF202" in r_csv.text

    r_ics = api_client.get("/schedules/export.ics")
    assert r_ics.status_code == 200
    assert "SEQUENCE:1" in r_ics.text
