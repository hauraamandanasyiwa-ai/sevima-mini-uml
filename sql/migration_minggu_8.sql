-- ============================================================================
-- Migrasi Database Minggu 8 — Modul Jadwal & Ruang Bagian 2
-- 1. Menambahkan kolom `sequence` pada tabel `jadwal` untuk ekspor iCalendar
-- 2. Membuat tabel `notification_outbox` untuk pola Transactional Outbox
-- ============================================================================

-- 1. Tambah kolom sequence pada jadwal (naik +1 setiap jadwal diperbarui)
ALTER TABLE jadwal
    ADD COLUMN sequence INT NOT NULL DEFAULT 0;

-- 2. Tabel Transactional Outbox (ditulis dalam transaksi yang sama dengan
--    perubahan jadwal & invalidasi KRS; dikirim setelah COMMIT oleh dispatcher)
CREATE TABLE IF NOT EXISTS notification_outbox (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    event_id    VARCHAR(64) NOT NULL,
    event_type  VARCHAR(40) NOT NULL,
    payload     JSON NOT NULL,
    status      VARCHAR(16) NOT NULL DEFAULT 'pending',
    attempts    INT NOT NULL DEFAULT 0,
    last_error  TEXT NULL,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    sent_at     DATETIME NULL,
    CONSTRAINT uq_outbox_event_id UNIQUE (event_id),
    CONSTRAINT ck_outbox_status CHECK (status IN ('pending', 'sent', 'failed')),
    INDEX idx_outbox_status_id (status, id)
);
