# ADR-002: Implementasi State Machine KRS (Tabel Transisi Sendiri vs Library)

- **Status:** Accepted
- **Tanggal:** Minggu 6 — Modul KRS Bagian 2 (SIMAK Mini)
- **Komponen:** `app/models/krs.py`, `app/services/krs_manager.py`

---

## 1. Konteks

KRS memiliki siklus hidup terbatas: `draft`, `submitted`, `approved`, dan `revision`.
Transisi status harus ditegakkan secara ketat agar:
- Tidak ada jalur pintas ilegal (seperti `draft → approved` atau `revision → approved` tanpa submit ulang).
- Tidak mungkin tersimpan kombinasi status mustahil (berbeda dari desain banyak kolom boolean `is_submitted`, `is_approved`, `is_revision`).
- Peran aktor (`mahasiswa` vs `dosen_pa`) dan kepemilikan (`dosen_pa_id` milik mahasiswa tersebut) diperiksa pada setiap transisi.

Dokumen tugas menyebut *state management library* di bagian tools, sehingga kita perlu memutuskan apakah memakai library eksternal atau menulis tabel transisi sendiri.

---

## 2. Alternatif yang Dipertimbangkan

### Alternatif 1: Library `python-statemachine` / `transitions`
- **Pro:** Mendukung guard, callback `on_enter`/`on_exit`, dan generator diagram otomatis.
- **Kontra:** Menambah dependensi eksternal serta lapisan abstraksi tambahan yang berpotensi menyulitkan integrasi langsung dengan ORM SQLAlchemy 2.0 dan menyembunyikan alur saat VIVA.

### Alternatif 2: Tabel Transisi Eksplisit (`dict[(KRSStatus, actor), frozenset[KRSStatus]]`) — **Dipilih**
- **Pro:**
  - Untuk **4 state dan 4 transisi**, satu dictionary sudah sangat jelas, mudah dibaca seperti kalimat, tanpa dependensi tambahan.
  - Enkapsulasi penuh melalui dua method di model `KRS`: `check_transition()` (dipakai sebelum validasi mahal pada `submit_krs`) dan `transition()` (satu-satunya tempat yang boleh mengubah `self.status`).
  - Sangat mudah diuji secara menyeluruh (32 kombinasi `4 × 4 × 2` via `itertools.product`) dan mudah dijelaskan baris demi baris saat VIVA.
- **Kontra:** Jika kelak state bertambah banyak (misalnya `cancelled`, `locked_after_deadline`, `masa_perubahan_krs`) dan membutuhkan banyak callback per transisi, perlu dipertimbangkan migrasi ke library.

---

## 3. Keputusan

1. Menggunakan satu kolom `Enum(KRSStatus)` dan **tabel transisi eksplisit** `KRS_TRANSITIONS` di `app/models/krs.py`.
2. Memisahkan `check_transition()` dan `transition()`, serta melarang seluruh service/router mengubah `krs.status` secara langsung.
3. Memisahkan otorisasi menjadi **2 lapis**:
   - Lapis 1 (Peran) pada tabel transisi (`409 Conflict` / `TransitionError` bila status salah).
   - Lapis 2 (Kepemilikan) pada `KRSManager` (`403 Forbidden` / `ForbiddenError` bila bukan Dosen PA mahasiswa tersebut atau bukan mahasiswa pemilik KRS).
4. Menjadikan `approved` sebagai *terminal state*.

---

## 4. Konsekuensi

- Nol dependensi tambahan untuk state machine.
- Seluruh 28 transisi ilegal teruji otomatis di `tests/test_state_machine.py`.
- Kode service tetap bersih dari detail HTTP berkat polimorfisme `KRSError.status_code`.
