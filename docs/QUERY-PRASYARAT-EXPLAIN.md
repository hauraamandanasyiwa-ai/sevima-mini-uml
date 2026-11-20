# Query Prasyarat (`NOT EXISTS`) & Optimasi Indeks (`EXPLAIN`)

## 1. Masalah & Jebakan Klasik Nilai Huruf

Aturan bisnis: *mata kuliah prasyarat harus sudah diambil pada semester sebelumnya dengan nilai minimal **C**.*

**Jebakan klasik buatan AI:**
```sql
-- SALAH! Perbandingan alfabet (ASCII): 'A' < 'B' < 'C' < 'D' < 'E'
WHERE kd.nilai >= 'C'
```
Perbandingan string tersebut justru **meloloskan `C`, `D`, `E`** dan **menolak `A` dan `B`** (terbalik total).

**Solusi yang diterapkan:**
Memetakan nilai huruf ke bobot numerik menggunakan tabel `skala_nilai` (`A=4.00`, `A-=3.70`, `B+=3.30`, `B=3.00`, `B-=2.70`, `C+=2.30`, `C=2.00`, `D=1.00`, `E=0.00`), lalu membandingkan angkanya: `sn.bobot >= 2.00`.

---

## 2. Query SQL `NOT EXISTS` (Single Query, Bebas N+1)

```sql
SELECT mk.kode_mk, mk.nama
FROM prerequisites p
JOIN mata_kuliah mk ON mk.kode_mk = p.kode_prasyarat
WHERE p.kode_mk = :kode_mk
  AND NOT EXISTS (
      SELECT 1
      FROM krs_detail kd
      JOIN krs k ON k.id = kd.krs_id
      JOIN skala_nilai sn ON sn.huruf = kd.nilai
      WHERE k.nim = :nim
        AND k.semester < :semester_aktif
        AND kd.kode_mk = p.kode_prasyarat
        AND sn.bobot >= 2.00
  )
ORDER BY mk.kode_mk;
```

Cara membaca dari luar ke dalam:
1. **Outer query** mengambil seluruh mata kuliah prasyarat dari mata kuliah `:kode_mk`.
2. **Subquery `NOT EXISTS`** mencari bukti kelulusan milik `:nim` pada semester sebelumnya (`k.semester < :semester_aktif` — valid karena `semester` bertipe fixed-length 5 karakter seperti `'20251'`) dengan bobot nilai minimal `2.00` (nilai `C`).
3. Jika bukti kelulusan **tidak ada**, nama mata kuliah prasyarat dikembalikan sebagai prasyarat yang belum terpenuhi.

---

## 3. Strategi Indeks (Kolom Equality Dulu, Range Belakangan)

Tabel `krs_detail` tumbuh paling cepat karena menyimpan seluruh mata kuliah yang pernah diambil semua mahasiswa lintas semester. Tanpa indeks, MySQL melakukan *Full Table Scan* (`type = ALL`) setiap kali mahasiswa menambah mata kuliah.

Kolom yang dipakai pada `WHERE` dan `JOIN`:
1. `prerequisites(kode_mk, kode_prasyarat)` → sudah tercakup otomatis oleh **Composite Primary Key**.
2. `krs(nim, semester)` → sudah tercakup otomatis oleh **`UNIQUE CONSTRAINT uq_krs_nim_semester`**. Urutan kolomnya tepat: `nim` (operator `=`) didahulukan, `semester` (operator rentang `<`) belakangan.
3. `krs_detail(krs_id, kode_mk)` → sudah tercakup otomatis oleh **`UNIQUE CONSTRAINT uq_krs_detail_krs_mk`**.
4. `skala_nilai(huruf)` → sudah tercakup oleh **Primary Key**.

> **Catatan:** Indeks mempercepat operasi baca (`SELECT`) tetapi memperlambat operasi tulis (`INSERT`/`UPDATE`/`DELETE`), sehingga kita tidak memasang indeks berlebihan di luar kolom `WHERE`/`JOIN` yang kritis.

---

## 4. Pembuktian dengan `EXPLAIN` (MySQL)

Jalankan script [sql/explain_benchmark.sql](../sql/explain_benchmark.sql) pada server MySQL Anda untuk mengambil tangkapan layar/bukti `EXPLAIN` sebelum dan sesudah indeks:

| Kondisi | Tabel | `type` pada `EXPLAIN` | Keterangan |
| :--- | :--- | :--- | :--- |
| **Sebelum Indeks** (`tmp_krs_no_idx`, `tmp_krs_detail_no_idx`) | `k`, `kd` | `ALL` | Full Table Scan — membaca seluruh baris tabel setiap request. |
| **Sesudah Indeks** (`uq_krs_nim_semester`, `uq_krs_detail_krs_mk`) | `k`, `kd`, `sn` | `range` / `ref` / `eq_ref` | Indeks terpakai — pencarian langsung mengarah ke baris milik NIM & MK terkait. |

---

## 5. Konsistensi Transaksi & Race Condition (`SELECT ... FOR UPDATE`)

Skenario: Budi sudah mengambil 21 SKS lalu menambah Statistika (3 SKS) dari laptop dan Basis Data (3 SKS) dari ponsel pada detik yang sama.
- **Tanpa row lock:** kedua request membaca total 21 SKS, keduanya menghitung 24 SKS, lolos `SKSValidator`, dan hasil akhir di DB menjadi **27 SKS**.
- **Solusi di `KRSManager.add_course()`:**
  1. Mengunci baris `krs` di awal transaksi dengan `.with_for_update()`.
  2. Validasi dan `INSERT` ke `krs_detail` berada dalam **satu transaksi** dengan **satu `commit()` di akhir**.
  3. Request kedua menunggu sampai request pertama `commit`, lalu membaca total 24 SKS dan ditolak dengan pesan spesifik.
  4. `UniqueConstraint(krs_id, kode_mk)` + penanganan `IntegrityError` (`rollback()` + pesan ramah) menjadi jaring pengaman terakhir untuk duplikasi.

> **Penting:** SQLite mengabaikan klausa `FOR UPDATE`. Pengujian *concurrency* / *row lock* wajib dilakukan di **MySQL (InnoDB)**.
