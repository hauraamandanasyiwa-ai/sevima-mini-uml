# ADR-003: Algoritma Deteksi Bentrok Jadwal (Grouping + Sort-and-Sweep vs Interval Tree)

- **Status:** Accepted
- **Tanggal:** Minggu 7 — Modul Jadwal & Ruang Bagian 1 (SIMAK Mini)
- **Komponen:** `app/services/conflict_detector.py`, `app/services/scheduling_service.py`

---

## 1. Konteks

Prompt langkah 1 dokumen tugas meminta fungsi `detect_schedule_conflicts` yang memeriksa pasangan jadwal lalu dioptimasi menggunakan **Interval Tree**.
Di sisi lain, deteksi bentrok 3 dimensi pada kampus hanya mungkin terjadi antara jadwal pada:
- **Hari yang sama & ruangan yang sama** (`room_conflict`), atau
- **Hari yang sama & dosen yang sama** (`lecturer_conflict`).

Kita perlu menentukan struktur data & algoritma yang tepat untuk ukuran data nyata SEVIMA Mini tanpa *over-engineering*.

---

## 2. Analisis Skala & Alternatif

### Angka Nyata Kampus
- Jumlah jadwal per semester: **~600 jadwal** (sekitar `600 × 599 / 2 ≈ 179.700` pasangan total jika dibandingkan seluruhnya secara naif — tetap selesai dalam hitungan milidetik di Python).
- Setelah dikelompokkan berdasarkan `(hari, ruangan_kode)` atau `(hari, dosen_id)`, satu kelompok umumnya hanya berisi **6–8 jadwal**.

### Alternatif yang Dipertimbangkan
1. **Naive Pairwise (`itertools.combinations`, $O(n^2)$):**
   - *Pro:* Sangat pendek, mudah dibuktikan benar.
   - *Kontra:* Membandingkan jadwal lintas hari dan lintas ruangan yang tidak mungkin bentrok.
   - *Peran:* **Dipertahankan** sebagai `detect_schedule_conflicts_naive()` untuk *differential testing* (oracle) terhadap versi teroptimasi.
2. **Grouping + Sort-and-Sweep ($O(n \log n + k)$) — Dipilih:**
   - *Pro:* Nol dependensi eksternal; mengelompokkan berdasarkan `(hari, ruangan_kode)` dan `(hari, dosen_id)` lewat satu kamus kunci, mengurutkan 6–8 item per kelompok, lalu menyapu dengan aturan `act.jam_selesai > cur.jam_mulai` (interval setengah terbuka).
   - *Kontra:* Kurang ideal jika kelak perlu jutaan query titik/rentang dinamis berulang kali tanpa membangun ulang list.
3. **Interval Tree (`intervaltree`, $O(\log n + k)$ per query):**
   - *Pro:* Sangat cepat untuk dataset besar dan ribuan query kandidat per detik (misal sistem peminjaman ruang lintas tahun atau CSP solver skala besar).
   - *Kontra:* Pada 6–8 jadwal per kelompok, overhead pembuatan tree tidak memberi keuntungan nyata dan menambah dependensi eksternal.

---

## 3. Keputusan

1. Menggunakan **Grouping + Sort-and-Sweep** (`detect_schedule_conflicts`) sebagai algoritma produksi untuk `GET /schedules/conflicts`, dan mempertahankan **Naive** (`detect_schedule_conflicts_naive`) sebagai pembanding di *differential testing* (Hypothesis).
2. Untuk `create_jadwal` dan `update_jadwal`, pemeriksaan bentrok dilakukan langsung di **SQL** memanfaatkan dua indeks gabungan `idx_jadwal_hari_ruangan(hari, ruangan_kode)` dan `idx_jadwal_hari_dosen(hari, dosen_id)`.
3. Menunda penggunaan `intervaltree` hingga beban query benar-benar membutuhkannya (seperti solver jadwal skala besar).

---

## 4. Konsekuensi

- Kedua versi (`naive` dan `sweep`) dijamin ekuivalen melalui `test_property_differential_sweep_matches_naive_exactly` di `tests/test_schedule_properties.py`.
- Tidak ada dependensi tambahan yang tidak perlu; optimasi berbasis pengukuran, bukan asumsi.
