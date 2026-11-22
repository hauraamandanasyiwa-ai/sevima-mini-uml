-- ============================================================================
-- Migrasi Database Minggu 11 — Modul Keuangan (SPP)
-- Tabel: payment_method, billing, payment
-- Status billing: unpaid, partial, paid, overdue
-- ============================================================================

CREATE TABLE IF NOT EXISTS payment_method (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    code        VARCHAR(24) NOT NULL,
    name        VARCHAR(80) NOT NULL,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_payment_method_code UNIQUE (code)
);

CREATE TABLE IF NOT EXISTS billing (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    nim         VARCHAR(20) NOT NULL,
    semester    CHAR(5) NOT NULL,
    amount      DECIMAL(12, 2) NOT NULL,
    denda       DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    paid_amount DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    due_date    DATE NOT NULL,
    status      ENUM('unpaid', 'partial', 'paid', 'overdue') NOT NULL DEFAULT 'unpaid',
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_billing_nim_semester UNIQUE (nim, semester),
    CONSTRAINT ck_billing_semester_len CHECK (LENGTH(semester) = 5),
    CONSTRAINT ck_billing_amount_nonneg CHECK (amount >= 0),
    CONSTRAINT ck_billing_denda_nonneg CHECK (denda >= 0),
    CONSTRAINT ck_billing_paid_nonneg CHECK (paid_amount >= 0),
    CONSTRAINT fk_billing_mhs FOREIGN KEY (nim) REFERENCES mahasiswa(nim) ON DELETE RESTRICT,
    INDEX idx_billing_nim_status (nim, status),
    INDEX idx_billing_due_status (due_date, status)
);

CREATE TABLE IF NOT EXISTS payment (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    billing_id        INT NOT NULL,
    payment_method_id INT NOT NULL,
    transaction_id    VARCHAR(64) NOT NULL,
    amount            DECIMAL(12, 2) NOT NULL,
    status            VARCHAR(20) NOT NULL DEFAULT 'paid',
    source            VARCHAR(20) NOT NULL DEFAULT 'manual',
    paid_at           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    note              TEXT NULL,
    CONSTRAINT uq_payment_transaction_id UNIQUE (transaction_id),
    CONSTRAINT ck_payment_amount_pos CHECK (amount > 0),
    CONSTRAINT fk_payment_billing FOREIGN KEY (billing_id) REFERENCES billing(id) ON DELETE CASCADE,
    CONSTRAINT fk_payment_method FOREIGN KEY (payment_method_id) REFERENCES payment_method(id) ON DELETE RESTRICT,
    INDEX idx_payment_billing_paid_at (billing_id, paid_at)
);
