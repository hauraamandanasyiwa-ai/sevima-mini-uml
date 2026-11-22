import logging
from contextlib import asynccontextmanager
from datetime import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from app.database import Base, SessionLocal, engine
from app.exceptions import BillingError, GradeError, KRSError, ScheduleError
from app.models.billing import Billing, BillingStatus, Payment, PaymentMethod  # noqa: F401
from app.models.grade import Grade, GradeHistory  # noqa: F401 - pastikan tabel terdaftar di metadata
from app.models.krs import (
    DEFAULT_SKALA_NILAI,
    KRS,
    KRSDetail,
    KRSStatus,
    MataKuliah,
    SkalaNilai,
)
from app.models.mahasiswa import Mahasiswa
from app.models.outbox import OutboxEvent  # noqa: F401 - pastikan tabel terdaftar di metadata
from app.models.schedule import Dosen, Jadwal, Kelas, Ruangan
from app.routers.billing import router as billing_router
from app.routers.conflict_resolver import router as conflict_resolver_router
from app.routers.grades import router as grades_router
from app.routers.krs import router as krs_router
from app.routers.schedule import router as schedule_router
from app.runtime import init_notification_runtime
from app.services.billing_scheduler import start_billing_scheduler, stop_billing_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

_DASHBOARD_HTML_PATH = Path(__file__).parent / "static" / "conflict_resolver.html"
_GRADES_PORTAL_HTML_PATH = Path(__file__).parent / "static" / "grades_portal.html"
_FINANCE_DASHBOARD_HTML_PATH = Path(__file__).parent / "static" / "finance_dashboard.html"


def seed_skala_nilai(session: Session) -> None:
    """Mengisi tabel skala_nilai jika belum ada agar query prasyarat siap pakai."""
    for huruf, bobot in DEFAULT_SKALA_NILAI.items():
        if session.get(SkalaNilai, huruf) is None:
            session.add(SkalaNilai(huruf=huruf, bobot=bobot))
    session.commit()


def seed_dummy_data(session: Session) -> None:
    """Mengisi data dummy KRS (Minggu 5 & 6) secara idempoten."""
    mahasiswa_spec = [
        ("20240001", "Budi Santoso", "Teknik Informatika", "PA001"),
        ("20240002", "Siti Rahma", "Teknik Informatika", "PA002"),
        ("20240003", "Rina Marlina", "Teknik Informatika", "PA001"),
        ("20240004", "Andi Wijaya", "Ekonomi Manajemen", "PA002"),
    ]
    for nim, nama, prodi, dosen_pa_id in mahasiswa_spec:
        if session.get(Mahasiswa, nim) is None:
            session.add(
                Mahasiswa(nim=nim, nama=nama, prodi=prodi, dosen_pa_id=dosen_pa_id)
            )

    courses_spec = [
        ("IF101", "Algoritma dan Pemrograman", 3, 1, time(8, 0), time(10, 30), True),
        ("MA101", "Kalkulus 1", 3, 2, time(8, 0), time(10, 30), True),
        ("IF201", "Struktur Data", 3, 3, time(8, 0), time(10, 30), True),
        ("MA201", "Kalkulus 2", 3, 4, time(8, 0), time(10, 30), True),
        ("IF202", "Basis Data", 3, 1, time(8, 0), time(10, 30), True),
        ("IF203", "Statistika", 3, 1, time(9, 0), time(11, 0), False),
        ("IF204", "Jaringan Komputer", 3, 1, time(10, 30), time(13, 0), True),
    ]
    for kode, nama, sks, hari, mulai, selesai, is_wajib in courses_spec:
        if session.get(MataKuliah, kode) is None:
            session.add(
                MataKuliah(
                    kode_mk=kode,
                    nama=nama,
                    sks=sks,
                    hari=hari,
                    jam_mulai=mulai,
                    jam_selesai=selesai,
                    is_wajib=is_wajib,
                )
            )
    session.flush()

    algoritma = session.get(MataKuliah, "IF101")
    kalkulus1 = session.get(MataKuliah, "MA101")
    struktur_data = session.get(MataKuliah, "IF201")
    kalkulus2 = session.get(MataKuliah, "MA201")

    if struktur_data and algoritma and algoritma not in struktur_data.prasyarat:
        struktur_data.prasyarat.append(algoritma)
    if kalkulus2 and kalkulus1 and kalkulus1 not in kalkulus2.prasyarat:
        kalkulus2.prasyarat.append(kalkulus1)

    budi_prev = session.scalars(
        select(KRS).where(KRS.nim == "20240001", KRS.semester == "20242")
    ).first()
    if budi_prev is None:
        budi_prev = KRS(
            nim="20240001",
            semester="20242",
            status=KRSStatus.APPROVED,
            dosen_pa_id="PA001",
        )
        session.add(budi_prev)
        session.flush()
        session.add_all(
            [
                KRSDetail(krs_id=budi_prev.id, kode_mk="MA101", nilai="B"),
                KRSDetail(krs_id=budi_prev.id, kode_mk="IF101", nilai="D"),
            ]
        )

    siti_prev = session.scalars(
        select(KRS).where(KRS.nim == "20240002", KRS.semester == "20242")
    ).first()
    if siti_prev is None:
        siti_prev = KRS(
            nim="20240002",
            semester="20242",
            status=KRSStatus.APPROVED,
            dosen_pa_id="PA002",
        )
        session.add(siti_prev)
        session.flush()
        session.add(KRSDetail(krs_id=siti_prev.id, kode_mk="IF101", nilai="C"))

    session.commit()


def seed_schedule_dummy_data(session: Session) -> None:
    """Mengisi data dummy Ruang, Dosen, Kelas, Jadwal, dan KRS aktif Rina (Minggu 7 & 8)
    secara idempoten.

    Sengaja menyertakan 2 konflik awal agar dashboard Conflict Resolver langsung
    memperlihatkan `room_conflict` dan `lecturer_conflict`, serta KRS APPROVED milik
    Rina yang mengambil IF202-A dan IF203-A agar demo invalidasi KRS -> `revision`
    dapat langsung ditunjukkan.
    """
    ruang_spec = [
        ("A101", "Ruang Kuliah A101", 40),
        ("B201", "Ruang Kuliah B201", 30),
        ("LAB1", "Laboratorium Komputer 1", 25),
    ]
    for kode, nama, kapasitas in ruang_spec:
        if session.get(Ruangan, kode) is None:
            session.add(Ruangan(kode=kode, nama=nama, kapasitas=kapasitas))

    dosen_spec = [
        ("0101018501", "Dr. Daniel Pratama"),
        ("0102028602", "Prof. Rina Kusuma"),
        ("0103038703", "Ir. Hendra Wijaya"),
    ]
    dosen_map: dict[str, Dosen] = {}
    for nidn, nama in dosen_spec:
        existing = session.scalars(select(Dosen).where(Dosen.nidn == nidn)).first()
        if existing is None:
            existing = Dosen(nidn=nidn, nama=nama)
            session.add(existing)
            session.flush()
        dosen_map[nidn] = existing

    kelas_spec = [
        ("IF202", "A", 35, "20251"),
        ("IF202", "B", 30, "20251"),
        ("IF203", "A", 25, "20251"),
        ("IF204", "A", 40, "20251"),
        ("IF101", "A", 35, "20251"),
    ]
    kelas_map: dict[tuple[str, str], Kelas] = {}
    for kode_mk, nama_kelas, kuota, sem in kelas_spec:
        existing = session.scalars(
            select(Kelas).where(
                Kelas.kode_mk == kode_mk,
                Kelas.nama_kelas == nama_kelas,
                Kelas.semester == sem,
            )
        ).first()
        if existing is None:
            existing = Kelas(
                kode_mk=kode_mk,
                nama_kelas=nama_kelas,
                kuota=kuota,
                semester=sem,
            )
            session.add(existing)
            session.flush()
        kelas_map[(kode_mk, nama_kelas)] = existing

    has_jadwal = session.scalars(select(Jadwal).limit(1)).first()
    if has_jadwal is None:
        d1 = dosen_map["0101018501"].id
        d2 = dosen_map["0102028602"].id
        d3 = dosen_map["0103038703"].id

        session.add_all(
            [
                # Jadwal #1: Basis Data A, Senin 08:00-09:40, A101, Dosen 1
                Jadwal(
                    kelas_id=kelas_map[("IF202", "A")].id,
                    ruangan_kode="A101",
                    dosen_id=d1,
                    hari=1,
                    jam_mulai=time(8, 0),
                    jam_selesai=time(9, 40),
                ),
                # Jadwal #2 (BERSAMBUNG, AMAN): Jaringan A, Senin 09:40-11:20, A101, Dosen 2
                Jadwal(
                    kelas_id=kelas_map[("IF204", "A")].id,
                    ruangan_kode="A101",
                    dosen_id=d2,
                    hari=1,
                    jam_mulai=time(9, 40),
                    jam_selesai=time(11, 20),
                ),
                # Jadwal #3 (SENGAJA ROOM CONFLICT dengan #1): Statistika A, Senin 08:30-10:00, A101, Dosen 3
                Jadwal(
                    kelas_id=kelas_map[("IF203", "A")].id,
                    ruangan_kode="A101",
                    dosen_id=d3,
                    hari=1,
                    jam_mulai=time(8, 30),
                    jam_selesai=time(10, 0),
                ),
                # Jadwal #4 (SENGAJA LECTURER CONFLICT dengan #1): Basis Data B, Senin 08:30-10:10, B201, Dosen 1
                Jadwal(
                    kelas_id=kelas_map[("IF202", "B")].id,
                    ruangan_kode="B201",
                    dosen_id=d1,
                    hari=1,
                    jam_mulai=time(8, 30),
                    jam_selesai=time(10, 10),
                ),
                # Jadwal #5 (AMAN, beda hari): Algoritma A, Rabu 08:00-09:40, A101, Dosen 1
                Jadwal(
                    kelas_id=kelas_map[("IF101", "A")].id,
                    ruangan_kode="A101",
                    dosen_id=d1,
                    hari=3,
                    jam_mulai=time(8, 0),
                    jam_selesai=time(9, 40),
                ),
            ]
        )

    # Seed KRS APPROVED milik Rina (20240003) pada semester 20251 agar demo
    # invalidasi KRS -> revision dan notifikasi mahasiswa langsung terlihat.
    rina_krs = session.scalars(
        select(KRS).where(KRS.nim == "20240003", KRS.semester == "20251")
    ).first()
    if rina_krs is None:
        rina_krs = KRS(
            nim="20240003",
            semester="20251",
            status=KRSStatus.APPROVED,
            dosen_pa_id="PA001",
        )
        session.add(rina_krs)
        session.flush()
        session.add_all(
            [
                KRSDetail(
                    krs_id=rina_krs.id,
                    kode_mk="IF202",
                    kelas_id=kelas_map[("IF202", "A")].id,
                ),
                KRSDetail(
                    krs_id=rina_krs.id,
                    kode_mk="IF203",
                    kelas_id=kelas_map[("IF203", "A")].id,
                ),
            ]
        )

    session.commit()


def ensure_minggu8_schema_upgrades() -> None:
    """Menambahkan kolom `sequence` pada tabel `jadwal` jika database lokal berasal
    dari Minggu 7 (SQLAlchemy `create_all` tidak menambahkan kolom baru pada tabel lama).
    """
    inspector = inspect(engine)
    if "jadwal" in inspector.get_table_names():
        columns = {col["name"] for col in inspector.get_columns("jadwal")}
        if "sequence" not in columns:
            with engine.begin() as conn:
                conn.execute(
                    text("ALTER TABLE jadwal ADD COLUMN sequence INTEGER NOT NULL DEFAULT 0")
                )


def seed_grades_dummy_data(session: Session) -> None:
    """Mengisi contoh data nilai awal (Minggu 9-10) secara idempoten agar portal
    nilai, perhitungan IPK/IPS, audit trail, dan transkrip PDF langsung siap didemokan.
    """
    from decimal import Decimal

    has_grade = session.scalars(select(Grade).limit(1)).first()
    if has_grade is not None:
        return

    seed_rows = [
        # Budi (20240001): multi-semester + 1 MK diulang (IF101: D -> A)
        ("20240001", "MA101", "20242", "B", Decimal("3.00"), Decimal("92.00"), "Prof. Rina Kusuma"),
        ("20240001", "IF101", "20242", "D", Decimal("1.00"), Decimal("80.00"), "Dr. Daniel Pratama"),
        ("20240001", "IF101", "20251", "A", Decimal("4.00"), Decimal("95.00"), "Dr. Daniel Pratama"),
        ("20240001", "IF202", "20251", "A-", Decimal("3.70"), Decimal("88.00"), "Dr. Daniel Pratama"),
        # Siti (20240002): contoh nilai sempurna Cum Laude
        ("20240002", "IF101", "20242", "A", Decimal("4.00"), Decimal("96.00"), "Dr. Daniel Pratama"),
        ("20240002", "MA101", "20242", "A", Decimal("4.00"), Decimal("94.00"), "Prof. Rina Kusuma"),
        ("20240002", "IF202", "20251", "A", Decimal("4.00"), Decimal("92.00"), "Dr. Daniel Pratama"),
    ]
    grades_created: list[Grade] = []
    for nim, kode_mk, sem, huruf, angka, presensi, actor in seed_rows:
        g = Grade(
            nim=nim,
            kode_mk=kode_mk,
            semester=sem,
            nilai_huruf=huruf,
            nilai_angka=angka,
            presensi_persen=presensi,
            updated_by=actor,
        )
        session.add(g)
        grades_created.append(g)
    session.flush()

    # Contoh 1 baris audit trail untuk Budi agar tabel riwayat langsung terlihat
    if grades_created:
        session.add(
            GradeHistory(
                grade_id=grades_created[0].id,
                old_value="B-",
                new_value="B",
                changed_by="Prof. Rina Kusuma",
                reason="Penyesuaian nilai tugas proyek akhir",
            )
        )
    session.commit()


def seed_billing_dummy_data(session: Session) -> None:
    """Mengisi metode pembayaran & contoh tagihan SPP (Minggu 11) secara idempoten."""
    from datetime import date, datetime, timezone
    from decimal import Decimal

    methods_spec = [
        ("VA_BCA", "Virtual Account BCA"),
        ("QRIS", "QRIS Nasional"),
        ("TRANSFER", "Transfer Bank"),
        ("CASH", "Loket Keuangan"),
    ]
    method_map: dict[str, PaymentMethod] = {}
    for code, name in methods_spec:
        existing = session.scalars(select(PaymentMethod).where(PaymentMethod.code == code)).first()
        if existing is None:
            existing = PaymentMethod(code=code, name=name, is_active=True)
            session.add(existing)
            session.flush()
        method_map[code] = existing

    if session.scalars(select(Billing).limit(1)).first() is not None:
        session.commit()
        return

    # Contoh tagihan lintas status (paid, partial, unpaid, overdue) untuk demo Dashboard Keuangan
    b_budi = Billing(
        nim="20240001",
        semester="20251",
        amount=Decimal("5000000.00"),
        denda=Decimal("0.00"),
        paid_amount=Decimal("5000000.00"),
        due_date=date(2025, 9, 15),
        status=BillingStatus.PAID,
    )
    b_siti = Billing(
        nim="20240002",
        semester="20251",
        amount=Decimal("5000000.00"),
        denda=Decimal("0.00"),
        paid_amount=Decimal("2500000.00"),
        due_date=date(2026, 12, 15),
        status=BillingStatus.PARTIAL,
    )
    b_rina = Billing(
        nim="20240003",
        semester="20251",
        amount=Decimal("5000000.00"),
        denda=Decimal("100000.00"),
        paid_amount=Decimal("0.00"),
        due_date=date(2025, 9, 15),
        status=BillingStatus.OVERDUE,
    )
    b_andi = Billing(
        nim="20240004",
        semester="20251",
        amount=Decimal("4000000.00"),
        denda=Decimal("0.00"),
        paid_amount=Decimal("4000000.00"),
        due_date=date(2025, 9, 15),
        status=BillingStatus.PAID,
    )
    session.add_all([b_budi, b_siti, b_rina, b_andi])
    session.flush()

    session.add_all(
        [
            Payment(
                billing_id=b_budi.id,
                payment_method_id=method_map["VA_BCA"].id,
                transaction_id="SEED-TRX-001",
                amount=Decimal("5000000.00"),
                status="paid",
                source="webhook",
                paid_at=datetime(2026, 10, 12, 9, 30, tzinfo=timezone.utc),
                note="Pelunasan SPP Semester 20251",
            ),
            Payment(
                billing_id=b_siti.id,
                payment_method_id=method_map["QRIS"].id,
                transaction_id="SEED-TRX-002",
                amount=Decimal("2500000.00"),
                status="paid",
                source="manual",
                paid_at=datetime(2026, 11, 5, 14, 15, tzinfo=timezone.utc),
                note="Cicilan pertama 50%",
            ),
            Payment(
                billing_id=b_andi.id,
                payment_method_id=method_map["TRANSFER"].id,
                transaction_id="SEED-TRX-003",
                amount=Decimal("4000000.00"),
                status="paid",
                source="webhook",
                paid_at=datetime(2026, 11, 10, 11, 0, tzinfo=timezone.utc),
                note="Pelunasan SPP Ekonomi",
            ),
        ]
    )
    session.commit()


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    ensure_minggu8_schema_upgrades()
    # Rangkai Observer + 3 Kanal + OutboxDispatcher SEKALI saat aplikasi start
    init_notification_runtime()
    with SessionLocal() as session:
        seed_skala_nilai(session)
        seed_dummy_data(session)
        seed_schedule_dummy_data(session)
        seed_grades_dummy_data(session)
        seed_billing_dummy_data(session)
    start_billing_scheduler()
    try:
        yield
    finally:
        stop_billing_scheduler()


app = FastAPI(
    title="SIMAK Mini — Modul Keuangan SPP (Minggu 11)",
    description=(
        "SEVIMA Mini terintegrasi (KRS Minggu 5-6 + Jadwal & Ruang Minggu 7-8 + "
        "Nilai & Transkrip Minggu 9-10 + Modul Keuangan SPP Minggu 11): Billing Generator "
        "& APScheduler Cron, Payment Workflow + HMAC Webhook Gateway + Email Receipt, "
        "Block KRS saat menunggak, Dashboard Keuangan Real-Time, dan AI Financial Insights."
    ),
    version="0.11.0",
    lifespan=lifespan,
)


@app.exception_handler(KRSError)
async def krs_error_handler(_: Request, exc: KRSError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=exc.body())


@app.exception_handler(ScheduleError)
async def schedule_error_handler(_: Request, exc: ScheduleError) -> JSONResponse:
    """Single exception handler polimorfik untuk `ScheduleError` dan semua turunannya."""
    return JSONResponse(status_code=exc.status_code, content=exc.body())


@app.exception_handler(GradeError)
async def grade_error_handler(_: Request, exc: GradeError) -> JSONResponse:
    """Single exception handler polimorfik untuk `GradeError` dan semua turunannya."""
    return JSONResponse(status_code=exc.status_code, content=exc.body())


@app.exception_handler(BillingError)
async def billing_error_handler(_: Request, exc: BillingError) -> JSONResponse:
    """Single exception handler polimorfik untuk `BillingError` dan semua turunannya."""
    return JSONResponse(status_code=exc.status_code, content=exc.body())


app.include_router(krs_router)
app.include_router(schedule_router)
app.include_router(conflict_resolver_router)
app.include_router(grades_router)
app.include_router(billing_router)


@app.get("/conflict-resolver", response_class=HTMLResponse, tags=["Conflict Resolver UI"])
def conflict_resolver_dashboard() -> HTMLResponse:
    """Halaman dashboard HTML sederhana untuk admin akademik menyelesaikan bentrok jadwal."""
    return HTMLResponse(_DASHBOARD_HTML_PATH.read_text(encoding="utf-8"))


@app.get("/grades-portal", response_class=HTMLResponse, tags=["Grades & Transcripts UI"])
def grades_portal_page() -> HTMLResponse:
    """Form web dosen untuk input/edit nilai, melihat IPK otomatis, audit trail, dan download PDF."""
    return HTMLResponse(_GRADES_PORTAL_HTML_PATH.read_text(encoding="utf-8"))


@app.get("/finance-dashboard", response_class=HTMLResponse, tags=["Finance & Billing UI"])
def finance_dashboard_page() -> HTMLResponse:
    """Dashboard Keuangan real-time (tagihan SPP, collection rate, grafik per bulan, webhook, AI insights)."""
    return HTMLResponse(_FINANCE_DASHBOARD_HTML_PATH.read_text(encoding="utf-8"))


@app.get("/health", tags=["Health"])
def health_check() -> dict[str, str]:
    return {"status": "ok", "module": "keuangan-spp-minggu-11"}
