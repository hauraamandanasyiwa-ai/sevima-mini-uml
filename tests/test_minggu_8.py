import json
from datetime import date, time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exceptions import ScheduleConflictError
from app.models.krs import KRS, KRSApprovalLog, KRSDetail, KRSStatus
from app.models.mahasiswa import Mahasiswa
from app.models.outbox import OutboxEvent, OutboxStatus
from app.models.schedule import Dosen, Jadwal, Kelas
from app.observers import (
    AdminObserver,
    EventType,
    LecturerObserver,
    LogChannel,
    NotificationLogEntry,
    OutboxDispatcher,
    ScheduleEvent,
    ScheduleSubject,
    StudentObserver,
    SQLAlchemyEnrollmentRepository,
)
from app.services.ai_rescheduler import AIReschedulerService, validate_ai_suggestions
from app.services.ical_exporter import export_schedules_to_ics
from app.services.scheduling_service import ScheduleData, SchedulingService


# ============================================================================
# Helper Stubs / Test Doubles (Spy, Broken Observer, Fake LLM)
# ============================================================================


class SpyObserver:
    name = "SpyObserver"

    def __init__(self) -> None:
        self.received: list[ScheduleEvent] = []

    def update(self, event: ScheduleEvent) -> None:
        self.received.append(event)


class BrokenObserver:
    name = "BrokenObserver"

    def update(self, event: ScheduleEvent) -> None:
        raise RuntimeError("SMS Gateway sedang mati!")


class FlakyObserver:
    """Gagal pada panggilan pertama, berhasil pada panggilan kedua."""

    name = "FlakyObserver"

    def __init__(self, fail_times: int = 1) -> None:
        self._remaining_failures = fail_times
        self.success_count = 0

    def update(self, event: ScheduleEvent) -> None:
        if self._remaining_failures > 0:
            self._remaining_failures -= 1
            raise RuntimeError("Gangguan sementara")
        self.success_count += 1


class FakeLLMClient:
    """LLM palsu yang deterministik, cepat, gratis, dan tidak memanggil API eksternal."""

    def __init__(self, response_text: str) -> None:
        self._response_text = response_text
        self.prompts_received: list[str] = []

    def complete(self, prompt: str) -> str:
        self.prompts_received.append(prompt)
        return self._response_text


# ============================================================================
# TES 1: Observer dipanggil tepat sekali (idempotent attach)
# ============================================================================


def test_observer_called_exactly_once_even_if_attached_twice() -> None:
    subject = ScheduleSubject()
    spy = SpyObserver()

    # Sengaja attach dua kali -> tidak boleh menimbulkan notifikasi ganda
    subject.attach(spy)
    subject.attach(spy)

    event = ScheduleEvent(
        event_type=EventType.SCHEDULE_CHANGED,
        before={"hari": 1, "jam_mulai": "08:00", "jam_selesai": "09:40", "ruangan_kode": "A101"},
        after={"hari": 3, "jam_mulai": "13:00", "jam_selesai": "14:40", "ruangan_kode": "A101"},
    )
    failed = subject.notify(event)

    assert failed == []
    assert len(spy.received) == 1
    assert spy.received[0].event_id == event.event_id


# ============================================================================
# TES 2: Observer yang gagal tidak menghentikan observer di belakangnya
# ============================================================================


def test_broken_observer_does_not_stop_subsequent_observers() -> None:
    subject = ScheduleSubject()
    broken = BrokenObserver()
    spy = SpyObserver()

    # Daftarkan observer rusak paling depan
    subject.attach(broken)
    subject.attach(spy)

    event = ScheduleEvent(event_type=EventType.SCHEDULE_DELETED, before={"jadwal_id": 99})
    failed = subject.notify(event)

    assert failed == ["BrokenObserver"]
    assert len(spy.received) == 1
    assert spy.received[0] == event


# ============================================================================
# TES 3: Integration Test — Ubah jadwal -> KRS APPROVED Rina jadi REVISION
#        + 1 baris Outbox + log 3 kanal (email, sms, push) setelah commit
# ============================================================================


def test_update_schedule_invalidates_rina_approved_krs_writes_outbox_and_notifies_3_channels(
    db_session: Session,
) -> None:
    # Siapkan mahasiswa Rina + KRS APPROVED yang mengambil IF202-A
    rina = Mahasiswa(
        nim="20240099",
        nama="Rina",
        prodi="Teknik Informatika",
        dosen_pa_id="PA001",
    )
    db_session.add(rina)
    k_bd_a = db_session.scalars(
        select(Kelas).where(Kelas.kode_mk == "IF202", Kelas.nama_kelas == "A")
    ).one()
    d1 = db_session.scalars(select(Dosen).where(Dosen.nidn == "0101018501")).one()
    d2 = db_session.scalars(select(Dosen).where(Dosen.nidn == "0102028602")).one()

    krs_rina = KRS(
        nim=rina.nim,
        semester="20251",
        status=KRSStatus.APPROVED,
        dosen_pa_id="PA001",
    )
    # KRS DRAFT milik Budi tidak boleh disentuh oleh invalidator
    krs_budi_draft = KRS(
        nim="20240001",
        semester="20251",
        status=KRSStatus.DRAFT,
        dosen_pa_id="PA001",
    )
    db_session.add_all([krs_rina, krs_budi_draft])
    db_session.flush()
    db_session.add_all(
        [
            KRSDetail(krs_id=krs_rina.id, kode_mk="IF202", kelas_id=k_bd_a.id),
            KRSDetail(krs_id=krs_budi_draft.id, kode_mk="IF202", kelas_id=k_bd_a.id),
        ]
    )
    db_session.commit()

    # Rangkai Observer + 3 Kanal Log + OutboxDispatcher
    history: list[NotificationLogEntry] = []
    channels = [
        LogChannel("email", shared_history=history),
        LogChannel("sms", shared_history=history),
        LogChannel("push", shared_history=history),
    ]
    repo = SQLAlchemyEnrollmentRepository(lambda: db_session)
    subject = ScheduleSubject()
    subject.attach(StudentObserver(enrollment_repo=repo, channels=channels))
    subject.attach(LecturerObserver(channels=channels))
    subject.attach(AdminObserver(channels=channels))
    dispatcher = OutboxDispatcher(subject=subject)

    service = SchedulingService(session=db_session, dispatcher=dispatcher)

    # Buat jadwal awal Senin 08:00-09:40 di A101 dengan dosen d1
    jadwal = service.create_jadwal(
        ScheduleData(k_bd_a.id, "A101", d1.id, 1, time(8, 0), time(9, 40))
    )

    # Pindahkan jadwal ke Rabu 13:00-14:40 DAN ganti dosen d1 -> d2
    updated = service.update_jadwal(
        jadwal.id,
        ScheduleData(k_bd_a.id, "A101", d2.id, 3, time(13, 0), time(14, 40)),
    )
    assert updated.sequence == 1

    # 1. Pastikan KRS Rina (APPROVED) kembali ke REVISION & tercatat di approval_log
    db_session.refresh(krs_rina)
    db_session.refresh(krs_budi_draft)
    assert krs_rina.status == KRSStatus.REVISION
    assert krs_rina.revision_note is not None
    assert krs_budi_draft.status == KRSStatus.DRAFT

    sys_logs = list(
        db_session.scalars(
            select(KRSApprovalLog).where(
                KRSApprovalLog.krs_id == krs_rina.id,
                KRSApprovalLog.actor_id == "system",
            )
        ).all()
    )
    assert len(sys_logs) == 1

    # 2. Pastikan tepat 1 baris Outbox tertulis dan sudah berstatus SENT
    outbox_rows = list(db_session.scalars(select(OutboxEvent)).all())
    assert len(outbox_rows) == 1
    assert outbox_rows[0].event_type == EventType.SCHEDULE_CHANGED.value
    assert outbox_rows[0].status == OutboxStatus.SENT.value

    # 3. Pastikan semua 3 kanal (email, sms, push) terkirim ke Rina, dosen lama d1,
    #    dosen baru d2, dan admin akademik
    channels_used = {entry.channel for entry in history}
    recipients = {entry.recipient for entry in history}
    assert channels_used == {"email", "sms", "push"}
    assert f"mahasiswa:{rina.nim}" in recipients
    assert f"dosen:{d1.id}" in recipients
    assert f"dosen:{d2.id}" in recipients
    assert "admin:akademik" in recipients


def test_failed_update_rolls_back_outbox_and_sends_no_notification(
    db_session: Session,
) -> None:
    """Bug klasik #1: jika update ditolak (409 conflict), TIDAK boleh ada outbox
    tertulis maupun notifikasi yang terkirim.
    """
    k_bd_a = db_session.scalars(
        select(Kelas).where(Kelas.kode_mk == "IF202", Kelas.nama_kelas == "A")
    ).one()
    k_bd_b = db_session.scalars(
        select(Kelas).where(Kelas.kode_mk == "IF202", Kelas.nama_kelas == "B")
    ).one()
    d1 = db_session.scalars(select(Dosen).where(Dosen.nidn == "0101018501")).one()
    d2 = db_session.scalars(select(Dosen).where(Dosen.nidn == "0102028602")).one()

    spy = SpyObserver()
    subject = ScheduleSubject()
    subject.attach(spy)
    service = SchedulingService(session=db_session, dispatcher=OutboxDispatcher(subject))

    j1 = service.create_jadwal(ScheduleData(k_bd_a.id, "A101", d1.id, 1, time(8, 0), time(9, 40)))
    service.create_jadwal(ScheduleData(k_bd_b.id, "A101", d2.id, 2, time(8, 0), time(9, 40)))

    # Pindah j1 ke slot j2 -> 409 Conflict -> rollback total
    with pytest.raises(ScheduleConflictError):
        service.update_jadwal(j1.id, ScheduleData(k_bd_a.id, "A101", d1.id, 2, time(8, 30), time(10, 0)))

    assert list(db_session.scalars(select(OutboxEvent)).all()) == []
    assert spy.received == []


# ============================================================================
# TES 4: 4-Stage Validator Saran AI dengan FakeLLMClient
# ============================================================================


def test_ai_rescheduler_filters_fictional_room_and_conflicting_slot_with_fake_llm(
    db_session: Session,
) -> None:
    k_bd_a = db_session.scalars(
        select(Kelas).where(Kelas.kode_mk == "IF202", Kelas.nama_kelas == "A")
    ).one()
    k_bd_b = db_session.scalars(
        select(Kelas).where(Kelas.kode_mk == "IF202", Kelas.nama_kelas == "B")
    ).one()
    d1 = db_session.scalars(select(Dosen).where(Dosen.nidn == "0101018501")).one()
    d2 = db_session.scalars(select(Dosen).where(Dosen.nidn == "0102028602")).one()

    # Jadwal #1 (target reschedule): IF202-A (kuota 35), Senin 08:00-09:40 di A101, d1
    j_target = Jadwal(
        kelas_id=k_bd_a.id,
        ruangan_kode="A101",
        dosen_id=d1.id,
        hari=1,
        jam_mulai=time(8, 0),
        jam_selesai=time(9, 40),
    )
    # Jadwal #2 (penghalang di Selasa 08:00-09:40 A101): akan membuat saran #3 bentrok!
    j_blocker = Jadwal(
        kelas_id=k_bd_b.id,
        ruangan_kode="A101",
        dosen_id=d2.id,
        hari=2,
        jam_mulai=time(8, 0),
        jam_selesai=time(9, 40),
    )
    db_session.add_all([j_target, j_blocker])
    db_session.commit()

    # Fake LLM sengaja membungkus JSON dengan teks pembuka + mengembalikan 3 saran:
    # 1) VALID (Rabu 08:00-09:40, A101 cap 40 >= 35, bebas bentrok)
    # 2) RUANGAN FIKTIF ("Z999" tidak ada di database)
    # 3) BENTROK (Selasa 08:30-10:10, A101 bertumpuk dengan j_blocker)
    fake_payload = "Berikut rekomendasi terbaik saya:\n" + json.dumps(
        [
            {
                "hari": 3,
                "jam_mulai": "08:00",
                "jam_selesai": "09:40",
                "ruangan_kode": "A101",
                "alasan": "Slot Rabu pagi bebas bentrok dan muat 40 kursi.",
            },
            {
                "hari": 4,
                "jam_mulai": "08:00",
                "jam_selesai": "09:40",
                "ruangan_kode": "Z999",
                "alasan": "Ruangan fiktif hasil halusinasi AI.",
            },
            {
                "hari": 2,
                "jam_mulai": "08:30",
                "jam_selesai": "10:10",
                "ruangan_kode": "A101",
                "alasan": "Slot ini ternyata bentrok dengan jadwal lain.",
            },
        ]
    )

    fake_llm = FakeLLMClient(fake_payload)
    rescheduler = AIReschedulerService(session=db_session, llm_client=fake_llm)
    results = rescheduler.suggest_alternatives(j_target.id)

    assert len(results) == 1
    assert results[0].hari == 3
    assert results[0].ruangan_kode == "A101"
    assert results[0].jam_mulai == time(8, 0)
    assert results[0].jam_selesai == time(9, 40)

    # Uji juga Saringan 1 (JSON rusak -> [] tanpa crash) & Saringan 3 (ruangan terlalu kecil B201 cap 30 < 35)
    assert validate_ai_suggestions("Maaf saya tidak bisa membantu.", db_session, j_target) == []
    too_small = json.dumps(
        [
            {
                "hari": 5,
                "jam_mulai": "08:00",
                "jam_selesai": "09:40",
                "ruangan_kode": "B201",
                "alasan": "Kapasitas B201 hanya 30, kurang dari kuota 35.",
            }
        ]
    )
    assert validate_ai_suggestions(too_small, db_session, j_target) == []


# ============================================================================
# TES 5: Outbox Retry + Kunci Idempotensi (tidak ada pesan ganda saat retry)
# ============================================================================


def test_outbox_retry_deduplicates_already_sent_channel_with_idempotency_key(
    db_session: Session,
) -> None:
    history: list[NotificationLogEntry] = []
    email_ch = LogChannel("email", shared_history=history)

    flaky = FlakyObserver(fail_times=1)
    subject = ScheduleSubject()
    subject.attach(AdminObserver(channels=[email_ch]))
    subject.attach(flaky)

    event = ScheduleEvent(
        event_type=EventType.SCHEDULE_CHANGED,
        before={"kode_mk": "IF202", "hari": 1, "jam_mulai": "08:00", "jam_selesai": "09:40", "ruangan_kode": "A101"},
        after={"kode_mk": "IF202", "hari": 2, "jam_mulai": "08:00", "jam_selesai": "09:40", "ruangan_kode": "A101"},
    )
    row = OutboxEvent.from_event(event)
    db_session.add(row)
    db_session.commit()

    dispatcher = OutboxDispatcher(subject=subject)

    # Run #1: AdminObserver sukses (kirim 1 email), FlakyObserver gagal -> status tetap PENDING, attempts=1
    stats1 = dispatcher.run(db_session)
    db_session.refresh(row)
    assert stats1["retried"] == 1
    assert row.status == OutboxStatus.PENDING.value
    assert row.attempts == 1
    assert len(history) == 1

    # Run #2: FlakyObserver kini sukses -> status SENT, dan AdminObserver TIDAK mengirim email ke-2!
    stats2 = dispatcher.run(db_session)
    db_session.refresh(row)
    assert stats2["sent"] == 1
    assert row.status == OutboxStatus.SENT.value
    assert flaky.success_count == 1
    assert len(history) == 1  # tetap 1 berkat kunci idempotensi!


# ============================================================================
# TES 6: Ekspor iCalendar (.ics) — CRLF, UID stabil, RRULE UNTIL UTC, SEQUENCE
# ============================================================================


def test_icalendar_export_format_and_sequence_increment(db_session: Session) -> None:
    k_bd_a = db_session.scalars(
        select(Kelas).where(Kelas.kode_mk == "IF202", Kelas.nama_kelas == "A")
    ).one()
    d1 = db_session.scalars(select(Dosen).where(Dosen.nidn == "0101018501")).one()

    service = SchedulingService(session=db_session)
    jadwal = service.create_jadwal(
        ScheduleData(k_bd_a.id, "A101", d1.id, 1, time(8, 0), time(9, 40))
    )

    ics_v0 = export_schedules_to_ics(
        [jadwal],
        semester_start=date(2025, 9, 1),
        semester_end=date(2025, 12, 20),
    )
    assert "\r\n" in ics_v0
    assert f"UID:jadwal-{jadwal.id}@sevima-mini.ac.id\r\n" in ics_v0
    assert "SEQUENCE:0\r\n" in ics_v0
    assert "DTSTART;TZID=Asia/Jakarta:20250901T080000\r\n" in ics_v0
    assert "RRULE:FREQ=WEEKLY;UNTIL=" in ics_v0
    assert "Z\r\n" in ics_v0

    # Ubah jadwal -> SEQUENCE naik menjadi 1 dengan UID yang tetap sama
    jadwal_v1 = service.update_jadwal(
        jadwal.id,
        ScheduleData(k_bd_a.id, "A101", d1.id, 3, time(10, 0), time(11, 40)),
    )
    ics_v1 = export_schedules_to_ics(
        [jadwal_v1],
        semester_start=date(2025, 9, 1),
        semester_end=date(2025, 12, 20),
    )
    assert f"UID:jadwal-{jadwal.id}@sevima-mini.ac.id\r\n" in ics_v1
    assert "SEQUENCE:1\r\n" in ics_v1


# ============================================================================
# TES 7: Conflict Resolver API + Role Guard + Prinsip Satu Pintu + .ics Endpoint
# ============================================================================


def test_conflict_resolver_role_guard_suggest_apply_and_ics_endpoint(
    api_client: TestClient,
    db_session: Session,
) -> None:
    # 1. Tanpa header admin_akademik -> ditolak 403 Forbidden
    r_forbidden = api_client.get("/admin/conflicts")
    assert r_forbidden.status_code == 403

    r_student = api_client.get("/admin/conflicts", headers={"X-Role": "mahasiswa"})
    assert r_student.status_code == 403

    admin_headers = {"X-Role": "admin_akademik"}

    # Siapkan 2 jadwal yang bentrok ruangan (simulasi data impor lama)
    k_bd_a = db_session.scalars(
        select(Kelas).where(Kelas.kode_mk == "IF202", Kelas.nama_kelas == "A")
    ).one()
    k_stat_a = db_session.scalars(
        select(Kelas).where(Kelas.kode_mk == "IF203", Kelas.nama_kelas == "A")
    ).one()
    d1 = db_session.scalars(select(Dosen).where(Dosen.nidn == "0101018501")).one()
    d2 = db_session.scalars(select(Dosen).where(Dosen.nidn == "0102028602")).one()

    j1 = Jadwal(kelas_id=k_bd_a.id, ruangan_kode="A101", dosen_id=d1.id, hari=1, jam_mulai=time(8, 0), jam_selesai=time(9, 40))
    j2 = Jadwal(kelas_id=k_stat_a.id, ruangan_kode="A101", dosen_id=d2.id, hari=1, jam_mulai=time(8, 30), jam_selesai=time(10, 0))
    db_session.add_all([j1, j2])
    db_session.commit()

    # 2. Admin melihat daftar bentrok
    r_conf = api_client.get("/admin/conflicts", headers=admin_headers)
    assert r_conf.status_code == 200
    assert r_conf.json()["total_conflicts"] == 1

    # 3. Admin meminta saran AI untuk j2
    r_sug = api_client.post(f"/admin/conflicts/{j2.id}/suggest", headers=admin_headers)
    assert r_sug.status_code == 200
    suggestions = r_sug.json()["suggestions"]
    assert 1 <= len(suggestions) <= 3

    # 4. Uji prinsip satu pintu: coba terapkan ke slot yang bentrok dengan j1 -> HTTP 409!
    r_409 = api_client.post(
        f"/admin/conflicts/{j2.id}/apply",
        headers=admin_headers,
        json={
            "hari": 1,
            "jam_mulai": "08:15",
            "jam_selesai": "09:45",
            "ruangan_kode": "A101",
        },
    )
    assert r_409.status_code == 409

    # 5. Terapkan saran pertama yang valid -> 200 OK & bentrok terselesaikan!
    chosen = suggestions[0]
    r_apply = api_client.post(
        f"/admin/conflicts/{j2.id}/apply",
        headers=admin_headers,
        json={
            "hari": chosen["hari"],
            "jam_mulai": chosen["jam_mulai"],
            "jam_selesai": chosen["jam_selesai"],
            "ruangan_kode": chosen["ruangan_kode"],
        },
    )
    assert r_apply.status_code == 200
    assert r_apply.json()["sequence"] == 1

    r_after = api_client.get("/admin/conflicts", headers=admin_headers)
    assert r_after.json()["total_conflicts"] == 0

    # 6. Endpoint ekspor kalender .ics & halaman dashboard HTML
    r_ics = api_client.get("/schedules/export.ics")
    assert r_ics.status_code == 200
    assert "text/calendar" in r_ics.headers["content-type"]
    assert "BEGIN:VCALENDAR" in r_ics.text

    r_ui = api_client.get("/conflict-resolver")
    assert r_ui.status_code == 200
    assert "Conflict Resolver Dashboard" in r_ui.text
