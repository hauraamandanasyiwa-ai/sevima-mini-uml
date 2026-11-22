# UML Sequence Diagram — Observer Pattern & Transactional Outbox (Minggu 8)

> **Deliverable Wajib (Minggu 8):** Diagram interaksi berikut disusun sesuai kode aktual pada `app/routers/schedule.py`, `app/services/scheduling_service.py`, `app/services/krs_invalidator.py`, `app/observers/outbox_dispatcher.py`, `app/observers/subject.py`, dan `app/observers/channels.py`.

## Alur Perubahan Jadwal (`PUT /schedules/{id}` atau `POST /admin/conflicts/{id}/apply`)

Perhatikan posisi **`COMMIT`** yang terjadi **SEBELUM** `OutboxDispatcher` memanggil `ScheduleSubject.notify(event)`. Dengan urutan ini, kegagalan validasi/commit tidak akan pernah mengirim notifikasi palsu, dan kegagalan salah satu observer tidak akan pernah membatalkan perubahan jadwal yang sudah sah.

```mermaid
sequenceDiagram
    autonumber
    actor Admin as Admin Akademik
    participant API as FastAPI Router
    participant Svc as SchedulingService
    participant Inv as KRSInvalidator
    participant DB as Database (SQLAlchemy)
    participant Disp as OutboxDispatcher
    participant Subj as ScheduleSubject
    participant Obs as Observer (Student / Lecturer / Admin)
    participant Ch as LogChannel (Email / SMS / Push)

    Admin->>API: PUT /schedules/{id} (atau POST /admin/conflicts/{id}/apply)
    API->>Svc: update_jadwal(jadwal_id, ScheduleData)

    rect rgb(239, 246, 255)
        Note over Svc,DB: Satu Transaksi Atomik (BEGIN)
        Svc->>DB: SELECT ruangan & dosen FOR UPDATE (urutan tetap)
        Svc->>DB: Cek bentrok 3D (exclude_id) & capacity check
        Svc->>DB: UPDATE jadwal (slot baru, sequence = sequence + 1)
        Svc->>Inv: invalidate_for_kelas(kelas_id, reason)
        Inv->>DB: SELECT krs WHERE status IN (submitted, approved)
        Inv->>DB: krs.transition(REVISION, "system") + INSERT krs_approval_log
        Svc->>DB: INSERT notification_outbox (status='pending', event_id unik)
        Svc->>DB: COMMIT
    end

    Note over Svc,Disp: COMMIT selesai — baru jalankan pengiriman notifikasi

    Svc->>Disp: run(session)
    Disp->>DB: SELECT * FROM notification_outbox WHERE status='pending' FOR UPDATE SKIP LOCKED
    Disp->>Subj: notify(ScheduleEvent)

    loop Untuk setiap observer (dibungkus try/except terpisah)
        Subj->>Obs: update(event)
        loop Untuk setiap kanal (email, sms, push)
            Obs->>Ch: send(recipient, subject, message, key=event_id:recipient:channel)
            Ch-->>Obs: True (tulis ke log) / False (skip jika duplikat)
        end
    end

    Subj-->>Disp: failed_observers ([])
    Disp->>DB: UPDATE notification_outbox SET status='sent', sent_at=NOW() + COMMIT
    Svc-->>API: ScheduleOut
    API-->>Admin: HTTP 200 OK (atau HTTP 409 jika bentrok/kapasitas penuh)
```

## Catatan Arsitektur Kunci untuk Viva

1. **Kenapa `COMMIT` sebelum `notify()`?**
   Jika `notify()` dipanggil sebelum `COMMIT` dan kemudian `COMMIT` gagal (mis. constraint DB atau deadlock), mahasiswa dan dosen sudah terlanjur menerima pemberitahuan tentang perubahan jadwal yang tidak pernah terjadi. Dengan Transactional Outbox, perubahan jadwal + invalidasi KRS + baris `notification_outbox` di-commit bersama-sama secara atomik.
2. **Bagaimana jika salah satu observer gagal (mis. SMS gateway mati)?**
   Setiap `observer.update(event)` dibungkus `try/except` terpisah sehingga observer lain tetap menerima notifikasi. `OutboxDispatcher` mencatat `attempts += 1` dan membiarkan baris tetap `pending` (maks 5 kali percobaan sebelum `failed`). Saat dicoba ulang, observer yang sebelumnya sudah sukses tidak mengirim pesan ganda karena setiap `LogChannel` memeriksa **kunci idempotensi** (`event_id:recipient:channel`).
3. **Di mana `attach()` dipanggil?**
   Di `app/runtime.py` (`init_notification_runtime()`) saat aplikasi FastAPI start (`lifespan`), **bukan** di dalam endpoint request — sehingga tidak ada kebocoran memori maupun duplikasi notifikasi saat request berulang.
