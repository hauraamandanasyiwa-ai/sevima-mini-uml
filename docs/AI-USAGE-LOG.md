# AI Usage Log — Modul KRS (Minggu 5 & Minggu 6)

Dokumen ini mencatat prompt kunci, proses review kritis, dan **revisi manual** sesuai **AI-First Charter** (hanya memakai data dummy seperti Budi, Siti, `PA001`, `PA002` — tidak pernah menempelkan data mahasiswa sungguhan).

---

## Bagian A — Minggu 5 (Skema, Chain of Responsibility, Query Prasyarat)

| No | Item Verifikasi Kritis | Status | Bukti di Kode |
| :--- | :--- | :---: | :--- |
| 1 | Arah `primaryjoin` & `secondaryjoin` pada `MataKuliah.prasyarat` benar (tidak terbalik) | LULUS | `app/models/krs.py`, `test_self_referencing_prerequisite_direction` |
| 2 | Bentrok jadwal memakai irisan interval (`mulai1 < selesai2 and mulai2 < selesai1`), bersambung tidak bentrok | LULUS | `app/validators/conflict.py`, `test_schedule_conflict_cases` |
| 3 | Perbandingan nilai memakai bobot numerik (`skala_nilai`), bukan string `nilai >= 'C'` | LULUS | `app/queries/prerequisite.py`, `test_prerequisite_validator_grade_weights_and_previous_semester` |
| 4 | Total tepat 24 SKS diizinkan; >24 ditolak menyebut angka | LULUS | `app/validators/sks.py`, `test_sks_validator_allows_exact_24_and_rejects_over` |
| 5 | Query prasyarat single-query `NOT EXISTS` bebas N+1 | LULUS | `app/queries/prerequisite.py` |

---

## Bagian B — Minggu 6 (State Machine, Approval ACID, Property-Based Testing)

### 1. Fitur & Tools
- **Fitur:** State Machine KRS (4 state, 4 transisi sah, 28 transisi ilegal), Otorisasi 2 lapis, Transaksi `approve_krs` / `revise_krs` (status + timestamp + log + notifikasi DB), Optimistic Locking `version`, Property-Based Testing (`hypothesis`), dan Challenge Opsional `KRSRecommender` (CSP Backtracking).
- **Prompt Kunci:**
  - Meminta implementasi tabel transisi eksplisit dengan aktor di setiap transisi, pengecekan kepemilikan kolom `dosen_pa_id`, penolakan KRS kosong saat submit, pesan error bahasa Indonesia yang jelas, dan tes parametrisasi untuk 28 transisi ilegal.
  - Meminta property-based test `hypothesis` (`max_examples=1000`) untuk SKS validator dan Conflict validator dengan fungsi verifikasi independen.

### 2. Revisi Manual Kritis terhadap Output AI
1. **Otorisasi 2 Lapis (Kepemilikan Dosen PA):**
   - *Masalah awal:* Rancangan awal hanya mengecek peran `"dosen_pa"` di tabel transisi sehingga dosen mana pun bisa menyetujui KRS mahasiswa lain.
   - *Revisi manual:* Menambahkan `_ensure_dosen_pa_owner()` yang memeriksa `krs.dosen_pa_id == dosen_pa_id` dan melempar `ForbiddenError` (`403`), terpisah dari `TransitionError` (`409`).
2. **Enkapsulasi `transition()` & Penolakan KRS Kosong:**
   - *Masalah awal:* `submit_krs` sempat mengizinkan KRS kosong dan menulis status secara langsung.
   - *Revisi manual:* Semua perubahan status wajib lewat `krs.transition()` dan `submit_krs` mengecek `check_transition()` → tolak KRS kosong → jalankan ulang `validate_krs()` sebelum transisi.
3. **Optimistic Locking saat Perubahan `krs_detail`:**
   - *Masalah awal:* Menambah/menghapus baris `krs_detail` tidak otomatis memicu `UPDATE` pada tabel `krs`, sehingga kolom `version` tidak naik.
   - *Revisi manual:* Menambahkan `krs.touch()` (memperbarui `updated_at`) di `add_course()` dan `remove_course()` agar `version` selalu naik.
4. **Property-Based Testing yang Benar-Benar Menguji Validator:**
   - *Masalah awal:* Tes naif hanya menjumlahkan daftar acak atau memakai fungsi `is_schedule_conflict()` yang sama dengan kode produksi.
   - *Revisi manual:* Menulis ulang di `tests/test_property_based.py`:
     - Properti SKS menyertakan **2 assert** (`total <= 24` saat diterima, DAN `total + sks > 24` saat ditolak).
     - Properti bentrok jadwal diverifikasi memakai fungsi himpunan menit independen `_occupied_slots()`.
