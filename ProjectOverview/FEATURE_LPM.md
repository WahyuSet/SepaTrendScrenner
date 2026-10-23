# FEATURE — Liquidity Pressure Model (LPM) & Lensa Smart Money

> **Status**: Spesifikasi siap dikerjakan (belum ada kode)
> **Dibuat**: 2026-10-21 · **Diperbarui**: 2026-10-21 (peta jalan Fase A/B/C di bagian 13, pertanyaan terbuka di bagian 14)
> **Target proyek**: `D:\Learning\SepaTrend` (Flask + yfinance + IDX Edge PRO API)
> **Bahasa UI**: Bahasa Indonesia

Dokumen ini adalah brief lengkap untuk sesi pengembangan berikutnya. Semua yang dibutuhkan (konsep, rumus, data, arsitektur, urutan kerja, kriteria selesai) ada di sini, jadi sesi baru tidak perlu membaca dokumen sumber.

---

## 1. Tujuan

Menambahkan indikator **LPM (Liquidity Pressure Model)** beserta tiga lensa pendampingnya ke modal detail saham:

| Lensa | Pertanyaan yang dijawab | Bentuk tampilan |
|---|---|---|
| **LPM** | Ke arah mana smart money bergerak? | Garis kumulatif di bawah chart harga |
| **Intensity** | Kapan bandar sedang agresif? | Histogram harian (tidak membaca arah) |
| **Vol Rotation** | Seberapa sehat perpindahan barang? | Histogram berwarna hijau / kuning / merah |
| **Pembacaan Fase** | Saham sedang di fase mana? | Badge + kalimat panduan |

Fitur ini **on-demand per saham** (dibuka dari modal), bukan screener massal, karena tiap hari bursa butuh 1 request API. Setelah tab ini selesai dan dikalibrasi, LPM diperluas sebagai **lensa konfirmasi** untuk kandidat dari empat screener yang ada (view "LPM Radar" dengan universe terbatas, lalu badge konfluensi di tabel screener). Lihat bagian 13.

### Batasan
- Rumus di dokumen ini adalah **rancangan kita sendiri**, disusun dari prinsip konsep LPM yang dipublikasikan (bagian 2). Ini bukan salinan rumus milik Bandar Metrics, dan rumus asli mereka tidak diketahui.
- Hanya memakai data yang memang kita punya aksesnya (IDX Edge PRO + yfinance).

---

## 2. Prinsip Konsep (ringkasan dokumen sumber)

Sumber asli: `D:\Learning\bandar\OverviewProject\` (`Cara Kerja LPM.md`, `Perilaku khas LPM.md`, `Divergensi, Sinyal Terkuat LPM.md`, `Ketebatasan LPM.md`, `Panduan LPM.pdf`).

**Cara kerja (3 keputusan desain):**
1. **Pisahkan dulu, baru ukur.** Baca *ukuran transaksi relatif* (nilai per order), bukan volume mentah. 1.000 lot dari 1 order ≠ 1.000 lot dari 100 order. Transaksi besar yang konsisten mencirikan smart money.
2. **Normalisasi ke harga dan konteks.** Yang diukur adalah *dominasi*: seberapa besar porsi dana smart money terhadap seluruh aktivitas saham itu di hari yang sama, bukan nominal Rupiah.
3. **Akumulasi.** Tekanan harian dijumlahkan jadi satu garis. Tekanan sesaat saling meniadakan, tekanan konsisten membentuk arah.

**Perilaku khas:**
- Cenderung bergerak **lebih dulu** dari harga (jeda bisa berhari-hari sampai berminggu-minggu).
- Bukan lot dan bukan value. Bisa berubah tajam walau volume biasa saja, dan sebaliknya.
- **Kemiringan lebih penting dari nilai absolut.** Posisi = apa yang sudah terjadi, kemiringan = apa yang sedang terjadi.
- Karena dinormalisasi, kemiringan **bisa dibandingkan antar saham**.

**Divergensi (sinyal terkuat):**
- **Akumulasi senyap (positif):** harga turun/datar, LPM naik.
- **Distribusi terselubung (negatif):** harga naik/rekor baru, LPM turun.

**Keterbatasan (wajib tampil di UI sebagai catatan):**
- Lebih andal untuk horizon panjang dibanding harian.
- Data pasar reguler (RG). Transaksi negosiasi (NG) besar bisa tidak tertangkap.
- Bukan ramalan. Probabilitas, bukan kepastian.

**Hirarki saat sinyal bertentangan:** LPM diutamakan. Intensity dan Vol Rotation adalah pertimbangan, bukan pembalik keputusan.

---

## 3. Sumber Data

### 3.1 Broker summary harian — IDX Edge PRO
Endpoint yang sudah dipakai proyek: `GET /api/broker-summary/{code}` (lihat `ProjectOverview/APISpecs.md` dan `screener/idx_api_client.py`).

Field per broker yang dipakai LPM:

| Field | Arti |
|---|---|
| `broker_code` | Kode broker |
| `bval` / `sval` | Nilai beli / jual (Rupiah) |
| `bfrq` / `sfrq` | Frekuensi beli / jual. Terverifikasi di Langkah 0: jumlah **transaksi (match)**, bukan order (bagian 12) |
| `nval` | Net value (`bval − sval`) |
| `nvol` | Net volume |

Parameter: `start_date`, `end_date` (YYYY-MM-DD), `all_data=true` (semua broker), `flow=all`.

**Kuota: 1.000 request/hari** (dicatat di tabel `quota_usage`). LPM butuh **1 request per saham per hari bursa**.

### 3.2 Harga harian — yfinance
`DataFetcher.fetch_single_ticker(ticker, period="1y", interval="1d")` di `screener/data_fetcher.py`. Index tanggal dari data harga dipakai sebagai **daftar hari bursa**, sehingga broker summary hanya diminta untuk tanggal yang benar-benar ada transaksinya (libur otomatis terlewati).

### 3.3 ⚠️ Langkah 0 — verifikasi API (WAJIB sebelum menulis kode lain)
Belum dipastikan:
1. Apakah `start_date = end_date = <satu hari>` mengembalikan data **hari itu saja**?
2. Apakah rentang beberapa hari mengembalikan **agregat** (kemungkinan besar) atau rincian per hari?
3. Seberapa jauh histori tersedia (coba tanggal 6 dan 12 bulan lalu)?
4. Apakah `bfrq`/`sfrq` selalu terisi (tidak 0/null) untuk saham likuid maupun tidak likuid?

Buat skrip `scratch/verify_broker_daily.py` (folder `scratch/` di-gitignore) yang memakai `IDXApiClient._make_request`, **maksimal 5 request**, lalu catat hasilnya di bagian 12 dokumen ini. Kalau poin 1 gagal, LPM harian tidak bisa dibangun dengan endpoint ini: hentikan dan laporkan ke user.

---

## 4. Rumus

Semua rumus dihitung per saham, per hari bursa `d`, dari daftar broker `b` hari itu. Semua parameter ada di satu dict `LPM_PARAMS` supaya mudah dituning.

### 4.1 Konteks harian
```
T_d  = (Σ_b bval_b + Σ_b sval_b) / 2            # turnover hari itu
F_d  = Σ_b bfrq_b + Σ_b sfrq_b                  # total order (dua sisi)
A_d  = (Σ_b bval_b + Σ_b sval_b) / F_d          # rata-rata nilai per order di saham ini, hari ini
```
`A_d` adalah kunci normalisasi. Karena dihitung per saham per hari, ia otomatis menetralkan level harga (saham Rp100 vs Rp10.000) dan keramaian (saham sepi vs ramai).

### 4.2 Bobot smart money per broker per sisi
```
r_buy_b  = (bval_b / bfrq_b) / A_d              # ukuran order beli broker b relatif ke pasar
r_sell_b = (sval_b / sfrq_b) / A_d

w(r) = clamp((r − R0) / (R1 − R0), 0, 1)        # R0 = 1.5, R1 = 4.0
```
- `r ≤ 1.5` → bobot 0 (ukuran order setara ritel)
- `r ≥ 4.0` → bobot 1 (ukuran order khas pelaku besar)
- Di antaranya naik linear
- Sisi dengan `frq = 0` dilewati (bobot 0)

### 4.3 Tekanan harian (dominasi)
```
SB_d = Σ_b w(r_buy_b)  × bval_b                 # nilai beli smart money
SS_d = Σ_b w(r_sell_b) × sval_b                 # nilai jual smart money

pressure_d = (SB_d − SS_d) / T_d                # ∈ [−1, +1], tanpa satuan
```
Pembagian dengan `T_d` adalah "dominasi lebih penting dari nominal": Rp100 juta yang menguasai saham sepi bisa lebih dominan dari Rp1 miliar di saham ramai.

### 4.4 Garis LPM (kumulatif)
```
LPM_{−1} = 0                                   # baseline virtual sebelum hari pertama
LPM_d    = LPM_{d−1} + 100 × pressure_d        # jadi LPM hari pertama = 100 × pressure hari pertama
```
**Level absolutnya tidak bermakna antar saham. Yang dibandingkan adalah kemiringannya.**

Hari tanpa data broker (gagal fetch) **atau tanpa transaksi** (`T_d = 0` atau `F_d = 0`) → `pressure_d = null`, LPM dibawa datar (`LPM_d = LPM_{d−1}`), dan hari itu ditandai `gap: true` di respons.

### 4.5 Kemiringan & tren
```
slope_n(t) = rata-rata (100 × pressure) selama n hari terakhir     # poin per hari; n = 5 (cepat) dan 20 (struktural)
θ_n(t)     = max(0.5, k × σ(t) / √n)                               # k = 1.0; σ = std 100 × pressure, 60 hari terakhir
```
- Tanpa gap, `slope_n` sama dengan `(LPM_t − LPM_{t−n}) / n`. Hari gap tidak ikut dirata-rata. `slope_n = null` kalau lebih dari separuh jendela kosong.
- **θ adaptif** (keputusan 2026-10-21, pertanyaan 3): `slope_n` adalah rata-rata n nilai harian, jadi standard error-nya `σ/√n`. θ = 1 standard error, tidak pernah di bawah 0,5. Alasan: di Langkah 0, besaran harian BBCA ±7–16 poin, jauh di atas θ tetap 0,5.

| Status | Syarat |
|---|---|
| `RISING` | `slope_5 > θ_5` dan `slope_20 > 0` |
| `FALLING` | `slope_5 < −θ_5` dan `slope_20 < 0` |
| `TURNING_UP` | `slope_5 > θ_5` tapi `slope_20 ≤ 0` |
| `TURNING_DOWN` | `slope_5 < −θ_5` tapi `slope_20 ≥ 0` |
| `FLAT` | selain di atas |

Kalau hari yang **benar-benar tersimpan** (bukan gap) kurang dari 20, tampilkan status `DATA_KURANG` dan jangan klasifikasikan tren maupun divergensi (garis tetap digambar). Panjang kalender tidak dihitung: 10 hari tersimpan di dalam kalender 80 hari tetap `DATA_KURANG` (bug ini ditemukan saat smoke test BBCA, 2026-10-21).

### 4.6 Divergensi
Jendela `W = 20` hari bursa:
```
price_chg_W = (Close_t / Close_{t−W} − 1) × 100        # persen
hh_W        = max(Close[t−4 .. t]) >= max(Close[t−W .. t−5])   # rekor jendela dibuat dalam 5 hari terakhir
```
| Divergensi | Syarat |
|---|---|
| `POSITIVE` (Akumulasi Senyap) | `price_chg_W ≤ +2%` **dan** `slope_20 > θ_20` |
| `NEGATIVE` (Distribusi Terselubung) | (`price_chg_W ≥ +5%` **atau** `hh_W`) **dan** `slope_20 < −θ_20` |
| `NONE` | selain di atas |

- `hh_W` dihitung atas 5 hari terakhir (bukan hanya hari rekor) supaya status tidak nyala-mati sehari sesudah rekor.
- Deret `divergence_markers` = tanggal saat status berubah ke POSITIVE/NEGATIVE, untuk ditandai di chart. Marker sejenis yang berjarak < 5 hari bursa dari marker sebelumnya dilewati (debounce).

### 4.7 Intensity (lensa "kapan", tidak membaca arah)
"Seberapa agresif bandar memecah order hari ini." Kita ukur sebagai konsentrasi transaksi di broker yang paling aktif bergerak net:
```
Top5_d   = 5 broker dengan |nval| terbesar hari itu
C_d      = Σ_{b∈Top5} (bfrq_b + sfrq_b) / F_d                       # porsi transaksi dari 5 broker itu
Int_d    = (C_d − mean(C_ref)) / max(std(C_ref), 0.01)               # z-score; C_ref = 20 hari sebelumnya (minimal 10)
```
| Kategori | Syarat |
|---|---|
| `SPIKE_EKSTREM` | `Int_d ≥ 2.5` |
| `SPIKE` | `Int_d ≥ 1.5` |
| `NORMAL` | selain itu |

**z-score, bukan rasio** (keputusan 2026-10-21, pertanyaan 4). Rasio `C_d / mean(C)` punya batas atas `1/mean(C)`. Di Langkah 0, top-5 BBCA sudah memegang 39–49% transaksi, jadi `SPIKE_EKSTREM` (rasio ≥ 2,5) praktis mustahil, dan di ASRM (86%) bahkan `SPIKE` mustahil. Batas bawah std 0,01 (1 poin persen) mencegah z meledak saat porsinya hampir konstan. Kurang dari 10 hari pembanding → `null`.

### 4.8 Vol Rotation (lensa "seberapa sehat")
Seberapa besar porsi turnover yang benar-benar berpindah tangan secara net, dibanding sekadar churn:
```
E_d = Σ_b |nval_b| / (2 × T_d)                          # ∈ [0, 1]
```
Warna ditentukan dari persentil `E_d` (mid-rank: yang lebih kecil + ½ yang sama) terhadap 60 hari sebelumnya, atau seluruh histori sebelumnya kalau kurang dari 60. Kurang dari 10 hari pembanding → `null`:
| Warna | Persentil | Arti |
|---|---|---|
| `HIJAU` | ≥ 60 | Perpindahan efisien |
| `KUNING` | 30 – 60 | Efisiensi mulai turun |
| `MERAH` | < 30 | Keramaian tinggi, perpindahan nyata rendah (mirip wash) |

### 4.9 Pembacaan Fase (dari `Panduan LPM.pdf`)
Evaluasi berurutan, pakai kondisi pertama yang cocok. "Spike berulang" = ≥2 hari `SPIKE`/`SPIKE_EKSTREM` dalam 10 hari terakhir. Warna VR = warna dominan 5 hari terakhir; kalau seri, ambil warna yang lebih buruk (MERAH > KUNING > HIJAU). "Harga" = `price_chg_20`.

Urutan dan syarat di bawah sudah memuat revisi yang disetujui 2026-10-21 (pertanyaan 6). Perbedaan dari rancangan awal ditandai ✱.

| Fase | Syarat | Pembacaan (teks UI) |
|---|---|---|
| **Data belum cukup** | tren `DATA_KURANG` | Butuh minimal 20 hari bursa untuk membaca tren LPM. |
| **5. Distribusi** | divergensi `NEGATIVE`, atau LPM `FALLING` dengan harga ≥ +5% ✱ (`TURNING_DOWN` tidak lagi masuk sini) | Divergensi negatif. Keramaian dimanfaatkan untuk keluar. Saat paling berbahaya ikut euforia. |
| **6. Markdown** ✱ | LPM `FALLING` dengan harga < +5% (fase baru; sebelumnya jatuh ke Netral) | LPM turun dan harga tidak menguat. Smart money sedang keluar, belum ada tanda akumulasi. |
| **2. Persiapan** | LPM `RISING`, spike berulang, VR `HIJAU`, **dan harga ≤ +5%** ✱ | Fase senyap beralih ke fase gerak. Timing terkuat dalam kerangka ini. |
| **1. Senyap** | divergensi `POSITIVE` ✱ (dievaluasi sesudah Persiapan, jadi syarat "tanpa spike berulang" tidak diperlukan lagi; POSITIVE + spike yang belum memenuhi Persiapan tidak lagi jatuh ke Netral) | Akumulasi senyap. Sabar, pantau tanda persiapan. |
| **4. Panas** | harga ≥ +5% **dan** (LPM `RISING`/`FLAT` dengan VR `KUNING`/`MERAH`, **atau** LPM `TURNING_DOWN`) ✱ | Efisiensi menurun di harga tinggi. Rawan jangka pendek meski akumulasi belum habis. |
| **3. Markup** | LPM `RISING` dan harga > +2% | Kenaikan sehat selama perpindahan masih efisien. Pantau pergeseran warna. |
| **Netral** | selain di atas | Belum ada pola fase yang jelas. |

Tambahan matriks kombinasi (tampil sebagai catatan kedua, bila cocok). "Intensity spike" = hari terakhir `SPIKE`/`SPIKE_EKSTREM`:
- LPM `FALLING` + Intensity spike → **Pelepasan Bertahap**: jangan baca spike sebagai sinyal beli.
- Intensity spike + LPM `FLAT`/`DATA_KURANG` → **Belum Bermakna**: tanpa arah, spike hanya tanda aktivitas.

---

## 5. Arsitektur

### 5.1 File baru
| File | Isi |
|---|---|
| `screener/lpm.py` | Fungsi murni (tanpa I/O): `compute_daily_metrics(brokers)`, `compute_lpm(daily_rows, closes)`, `classify_trend`, `detect_divergence`, `compute_intensity`, `compute_vol_rotation`, `classify_phase`, dan `LPM_PARAMS`. Input/output berupa list/dict biasa supaya mudah dites. |
| `tests/test_lpm.py` | Unit test `unittest` (tidak perlu dependency baru) dengan data sintetis (bagian 8). |
| `screener/lpm_service.py` | Orkestrasi (tahap 3): kalender hari bursa dari yfinance (cache 10 menit per proses), sinkron hari terbaru, thread backfill. Route di `app.py` hanya menerjemahkan ke HTTP. |
| `tests/test_broker_daily.py`, `tests/test_lpm_service.py` | Test penyimpanan, backfill, status job, dan ketiga route dengan HTTP dan yfinance palsu. |
| `static/js/core/lpm_panel.js` | Halaman LPM: pemilih saham, daftar histori tersimpan, chart, kartu, tabel, backfill & polling. |
| `static/css/components/lpm_panel.css` | Style halaman LPM memakai token di `.agent/Design.md`. |
| `templates/views/view_lpm.html` | Halaman menu "LPM & Smart Money" (pindah dari modal, 2026-10-22). |

### 5.2 File yang diubah
| File | Perubahan |
|---|---|
| `screener/idx_api_client.py` | Tabel baru `broker_daily` + method `get_broker_daily(ticker, date)` dan `backfill_broker_daily(ticker, dates, max_requests)`. |
| `app.py` | Route `GET /api/idx/lpm/<ticker>`, `POST /api/idx/lpm/<ticker>/backfill`, `GET /api/idx/lpm/<ticker>/status`. Semua dengan `@admin_required` dan `is_valid_idx_ticker`. |
| `templates/modals/modal_stock_detail.html` | Tombol "Buka LPM" di footer modal → `openLpmPage(ticker)`. (Awalnya tab ke-4; dipindah ke menu sendiri 2026-10-22.) |
| `templates/components/sidebar.html`, `static/js/main.js` | Item menu `nav-lpm` (badge = jumlah saham dengan histori) dan view `view-lpm` di `switchScreener('lpm')`. |
| `templates/index.html` | Muat `lightweight-charts@5.2.1`, `lpm_panel.js`, dan `lpm_panel.css`. |

### 5.3 Penyimpanan — tabel `broker_daily`
Data broker hari yang sudah lewat **tidak berubah**, jadi disimpan permanen (beda dengan cache harian yang ada sekarang):
```sql
CREATE TABLE IF NOT EXISTS broker_daily (
    ticker     TEXT,
    date       TEXT,            -- YYYY-MM-DD
    data       TEXT,            -- JSON list broker mentah (broker_code, broker_name, bval, sval, bvol, svol, bfrq, sfrq, nval, nvol); lihat bagian 12
    status     TEXT,            -- 'ok' | 'empty' | 'error'
    fetched_at TEXT,            -- ISO, WIB
    attempts   INTEGER DEFAULT 0,  -- jumlah request untuk tanggal ini
    note       TEXT,            -- alasan error (mis. 'HTTP 500', tanggal respons tidak cocok)
    PRIMARY KEY (ticker, date)
);
```
- `status='empty'`: API sukses tapi tidak ada broker (misalnya saham disuspensi). Jangan di-fetch ulang.
- `status='error'`: dicoba ulang di backfill berikutnya, maksimal `LPM_PARAMS["max_fetch_attempts"]` = 3 kali per tanggal, supaya tanggal yang selalu gagal tidak menghabiskan kuota. Sesudah itu tanggal tersebut tampil sebagai gap.
- Di `data` hanya disimpan field di `BROKER_DAILY_FIELDS` (`screener/idx_api_client.py`), bukan respons mentah.

**Method di `IDXApiClient`** (tahap 2, selesai 2026-10-21):
| Method | Isi |
|---|---|
| `is_day_final(date)` | Tanggal lampau, atau hari ini setelah 17:00 WIB |
| `load_broker_daily(ticker, dates=None)` | Baca baris tersimpan. Tanpa request |
| `missing_broker_days(ticker, dates)` | Tanggal yang masih perlu request (belum ada, atau error di bawah batas coba), terbaru dulu |
| `get_broker_daily(ticker, date)` | Dari tabel kalau ada, kalau tidak 1 request + validasi + simpan. `None` untuk hari yang belum final |
| `backfill_broker_daily(ticker, dates, max_requests, on_progress, delay)` | Ambil tanggal yang hilang, terbaru dulu. `stopped_reason`: `done` / `max_requests` / `quota_reserve` / `quota_exhausted` |
| `_request_with_status(endpoint, params)` | Seperti `_make_request` tapi juga mengembalikan status HTTP. `_make_request` sekarang memanggil ini dan perilakunya tidak berubah |
- Hari ini (`date == today` WIB) **diabaikan sama sekali** sampai pukul 17:00 WIB: tidak diminta ke API, tidak disimpan, tidak masuk garis (keputusan 2026-10-21, pertanyaan 7). Ini menghemat kuota di jam bursa dan mencegah garis berubah-ubah karena data setengah hari. Semua perbandingan waktu memakai WIB (`timezone(timedelta(hours=7))`, pola `get_idx_market_status`), bukan jam server.
- Sebelum disimpan, respons divalidasi: `broker_start_date == broker_end_date == tanggal yang diminta` (bagian 12).

### 5.4 Strategi kuota
- Histori default: **80 hari bursa** (`LPM_PARAMS["history_days"]`): 60 hari tampilan + 20 hari warm-up untuk Intensity dan Vol Rotation (keputusan 2026-10-21, pertanyaan 5).
- Backfill pertama 1 saham ≈ 80 request. Setelah itu cukup **1 request per hari**.
- **Cadangan kuota**: backfill tidak pernah membuat request yang membuat sisa kuota turun di bawah 200 (`LPM_PARAMS["quota_reserve"]`), supaya fitur lain (broker summary, financials, analysis) tetap jalan. Sisa kuota saat berhenti = tepat 200.
- Backfill berjalan di **thread background** (pola sama dengan `background_scan_worker` di `app.py`), mulai dari tanggal terbaru ke terlama, sehingga garis langsung bisa digambar dari data yang sudah ada.
- Beri jeda ±0,3 detik antar request.
- Satu saham hanya boleh punya satu backfill aktif. Status job disimpan di **tabel SQLite `lpm_jobs`**, bukan di dict proses, karena Gunicorn berjalan dengan 3 worker (`deploy/tirexxz.service`) dan polling `/status` bisa jatuh ke worker lain. Klaim job memakai `BEGIN IMMEDIATE` supaya dua worker tidak bisa sama-sama memulai. Thread memperbarui `updated_at` setiap request; job `running` tanpa kabar lebih dari 120 detik dianggap mati (dilaporkan `error`) dan boleh dimulai ulang.
- Bar yfinance dengan volume 0 (suspensi, tidak ada transaksi) tidak diminta ke API dan tampil sebagai gap.

---

## 6. API

### `GET /api/idx/lpm/<ticker>`
Menghitung dari data yang **sudah tersimpan**. Kalau ada hari bursa terbaru yang belum tersimpan, maksimal **5 hari** (`LPM_PARAMS["max_sync_fetch_days"]`) diambil langsung saat request ini (keputusan 2026-10-21, pertanyaan 8). Kekurangan yang lebih banyak ditandai di `coverage` dan dilengkapi lewat backfill.

Aturan sinkron (tahap 3):
- Hanya tanggal yang **lebih baru dari hari terakhir yang tersimpan**. Lubang lama diisi lewat backfill.
- Saham tanpa histori sama sekali: **0 request**. User memulai backfill sendiri dari tombol.
- Saat backfill saham itu sedang berjalan: 0 request (thread backfill sudah mengambilnya).

Field `coverage` yang sebenarnya: `requested_days`, `available_days`, `gap_days`, `missing_days`, `synced_days`, `complete`, `has_history`. Respons juga memuat `ticker`, `backfill` (isi sama dengan `/status`), dan setiap baris `series` membawa `open`/`high`/`low`/`close` untuk candlestick serta `low_liquidity`.

```json
{
  "status": "success",
  "data": {
    "ticker": "BBCA",
    "as_of": "2026-10-20",
    "coverage": { "requested_days": 60, "available_days": 58, "gap_days": 2, "complete": false },
    "series": [
      {
        "date": "2026-10-20",
        "close": 9875,
        "pressure": 0.084,
        "lpm": 142.3,
        "intensity": 1.72,
        "intensity_level": "SPIKE",
        "vr_efficiency": 0.31,
        "vr_color": "HIJAU",
        "gap": false
      }
    ],
    "trend": { "status": "RISING", "slope_5": 9.8, "slope_20": 6.1, "theta_5": 3.4, "theta_20": 1.7 },
    "divergence": { "status": "POSITIVE", "price_chg_20": -1.4, "new_high_recent": false, "markers": [{ "date": "2026-10-02", "type": "POSITIVE" }] },
    "phase": { "id": "SENYAP", "label": "1. Senyap", "reading": "Akumulasi senyap. Sabar, pantau tanda persiapan.", "secondary": null },
    "top_smart_brokers": [{ "broker_code": "BK", "net_smart_value": 73400000000, "days_active": 14 }],
    "params": { "R0": 1.5, "R1": 4.0, "theta_k": 1.0, "theta_floor": 0.5, "window": 20 },
    "disclaimer": "Pembacaan perilaku dan probabilitas, bukan rekomendasi beli/jual. Berbasis data broker summary IDX."
  },
  "quota": { "used": 312, "remaining": 688, "limit": 1000 }
}
```
- `top_smart_brokers`: 5 broker dengan akumulasi `w × nilai` net terbesar selama jendela. Berguna untuk menjelaskan *siapa* di balik garis LPM.
- `coverage.complete = false` → UI menampilkan tombol "Lengkapi histori".

### `POST /api/idx/lpm/<ticker>/backfill`
Body opsional: `{ "days": 80 }` (dibatasi 20–250). Memulai thread backfill, lalu langsung mengembalikan `{ "status": "started", "missing_days": 42, "estimated_requests": 42, "quota": {...} }`. `estimated_requests` = `min(missing_days, sisa kuota − 200)`.
- Sudah berjalan → `"status": "running"`.
- Tidak ada yang hilang → `"status": "complete"`.
- Sisa kuota tidak cukup di atas cadangan → `409` dengan `"code": "QUOTA_RESERVE"` dan pesan Bahasa Indonesia.
- `days` bukan angka → `400`. Data harga tidak ada → `404`.

### `GET /api/idx/lpm/<ticker>/status`
`{ "state": "idle|running|done|stopped_quota|error", "done": 30, "total": 42, "requested": 30, "last_error": null, "started_at": "...", "updated_at": "...", "quota": {...} }`. Frontend mem-polling endpoint ini setiap 2 detik selama backfill berjalan.

---

## 7. UI — Halaman "LPM & Smart Money" (awalnya tab modal, lihat catatan "Dipindah ke menu sendiri")

Ikuti `.agent/Design.md` (Enterprise Clear White, token CSS, font yang sudah ada). Tidak ada warna atau ukuran hard-coded di luar token.

**Library chart:** `lightweight-charts@5.2.1` dari CDN (`https://unpkg.com/lightweight-charts@5.2.1/dist/lightweight-charts.standalone.production.js`, rilis 2026-08-12). Versi wajib dikunci persis, tidak boleh `@latest`. Dipilih v5 (pertanyaan 10) karena punya **native pane**: panel-panel berbagi satu sumbu waktu dan crosshair tanpa kode sinkronisasi manual (`addSeries(..., paneIndex)`, `pane.setStretchFactor(75/25)`, `createSeriesMarkers`). Chart dihancurkan (`chart.remove()`) saat ganti saham. Warna chart dibaca dari token CSS lewat `getComputedStyle`. Kalau CDN gagal, area chart menampilkan pesan dan kartu ringkasan tetap berlaku.

**Implementasi (tahap 4, 2026-10-22):** `static/js/core/lpm_panel.js`, `static/css/components/lpm_panel.css`, awalnya sebagai tab ke-4 di modal detail saham.

**Dipindah ke menu sendiri (2026-10-22, permintaan user):** chart LPM butuh ruang lebar, jadi LPM sekarang halaman penuh `templates/views/view_lpm.html` dari item sidebar "LPM & Smart Money" (bagian Portofolio & Tools). Isinya: pemilih kode saham (datalist 941 emiten, validasi 4 huruf dan terdaftar di BEI), chip saham yang sudah punya histori (`GET /api/idx/lpm`, tanpa kuota), lalu panel yang sama seperti di bawah dengan chart 520px; di layar ≥ 1440px tabel broker berdampingan dengan chart. Saham terakhir diingat di `localStorage` (`lpm:lastTicker`). Modal detail saham kembali 3 tab dan mendapat tombol "Buka LPM" yang menutup modal dan membuka halaman ini untuk saham tersebut; halaman LPM punya tombol "Detail saham" untuk arah sebaliknya.

Detail yang ditetapkan saat implementasi:
- Hari gap: garis LPM berwarna abu-abu (`--text-muted`) dan batang lensa kosong.
- Intensity memakai token biru yang sudah ada (`--status-div-hid-text`) dengan tiga tingkat kepekatan (pertanyaan 11), plus garis putus-putus di ambang spike 1,5. Vol Rotation memakai token status hijau/kuning/merah.
- Legend di atas chart menampilkan nilai di posisi crosshair (tanggal, close, LPM, pressure, lensa aktif).
- Tombol Refresh di header modal = ambil ulang GET (hitung ulang dari data tersimpan + sinkron maksimal 5 hari baru), bukan backfill (pertanyaan 12).
- Selama backfill: progress bar dari polling `/status` tiap 2 detik, dan garis digambar ulang tiap ±10 detik dari data yang sudah masuk.
- Layar ≤ 768px: bar tab modal bisa digeser horizontal, kartu ringkasan 2 kolom, chart 380px. Layar ≤ 480px: padding modal dikecilkan (berlaku untuk semua tab modal) supaya chart selebar ±290px di ponsel 375px (pertanyaan 14: layout mobile yang sudah ada yang berlaku, bukan "desktop-only" di `.agent/Design.md`).

**Susunan dari atas ke bawah:**
1. **Kartu ringkasan (4 kotak):** Tren LPM (badge + panah), Divergensi, Fase, Kemiringan 5H/20H (angka mono).
2. **Kalimat pembacaan fase** + catatan sekunder bila ada.
3. **Chart 2 panel dengan sumbu waktu yang disinkronkan** (awalnya 3 panel; garis LPM digabung ke panel harga atas permintaan user, 2026-10-22):
   - Panel atas (±75%): candlestick harga (sumbu kanan, Rupiah) **dan** garis LPM kumulatif (sumbu kiri, poin, warna gelap `--text-primary` supaya tidak tertukar dengan candle hijau), ditambah marker panah di tanggal divergensi (hijau = positif, merah = negatif). Keterangan chart menegaskan bahwa titik silang garis dan candle tidak bermakna karena satuannya berbeda; yang dibaca adalah arah keduanya.
   - Panel bawah (±25%): histogram Intensity **atau** Vol Rotation (hijau/kuning/merah), dipilih lewat toggle kecil.
   - Hari `gap` ditampilkan putus-putus/abu-abu, bukan disembunyikan.
4. **Tabel "Broker di balik LPM"**: 5 baris `top_smart_brokers`.
5. **Baris coverage:** "58 dari 60 hari bursa tersedia · sisa kuota 688". Ada tombol **Lengkapi histori** dengan progress bar saat backfill berjalan.
6. **Catatan keterbatasan** (teks kecil, selalu tampil): horizon panjang lebih andal; ukuran transaksi dibaca dari frekuensi = jumlah transaksi (match), bukan order; cakupan board (RG/NG) mengikuti data broker summary dan belum bisa dipastikan (bagian 12); bukan ramalan.

**State yang wajib ada:**
- Loading: skeleton seukuran chart.
- Belum ada histori sama sekali: penjelasan singkat + tombol mulai backfill + estimasi jumlah request.
- `DATA_KURANG` (< 20 hari): garis tetap digambar, kartu tren berlabel "Data belum cukup".
- Kuota habis: pesan jelas, tombol nonaktif.
- Error API: pesan + tombol coba lagi.

---

## 8. Pengujian

`tests/test_lpm.py` (jalankan: `python -m unittest tests.test_lpm`). Bangun data broker sintetis 40 hari:

| Skenario | Data sintetis | Harapan |
|---|---|---|
| Netral | Semua broker ukuran order ≈ `A_d` | `pressure ≈ 0`, tren `FLAT` |
| Akumulasi senyap | Harga datar; 2 broker order besar (r ≈ 6) net beli tiap hari | tren `RISING`, divergensi `POSITIVE`, fase `SENYAP` |
| Distribusi terselubung | Harga naik 8%; broker order besar net jual | tren `FALLING`, divergensi `NEGATIVE`, fase `DISTRIBUSI` |
| Invariansi harga | Skenario akumulasi dengan semua harga & nilai ×100 | Deret `pressure` identik (toleransi 1e-9) |
| Invariansi keramaian | Tambah broker ritel kecil yang beli & jual seimbang, **dengan broker besar sudah di `r ≥ R1` sebelum dan sesudah** | Tanda `pressure` tidak berubah, besarnya mengecil (dominasi turun). Kalau `r` broker besar di antara R0 dan R1, transaksi kecil tambahan menurunkan `A_d` dan bisa menaikkan bobotnya, jadi ekspektasi ini tidak berlaku. |
| Frekuensi nol | Broker dengan `bfrq = 0` | Tidak error, sisi itu berbobot 0 |
| Gap | Hari ke-15 tanpa data | `gap: true`, LPM datar di hari itu |
| Spike | Hari ke-30, porsi transaksi top-5 melonjak dari ±20% ke 60% | `intensity_level = SPIKE_EKSTREM` |
| Spike dengan konsentrasi tinggi | Porsi dasar ±45%, melonjak ke 95% (rasio lama hanya 2,1) | `SPIKE_EKSTREM` (regresi untuk alasan pindah ke z-score) |
| Fixture nyata | `scratch/lpm_fixtures/` dari Langkah 0 (dilewati kalau folder tidak ada) | BBCA 20 Okt `pressure ≈ +0,159`; ASRM `F_d = 70` |

Selain skenario di atas, `tests/test_lpm.py` juga menguji tabel tren, θ adaptif, slope dengan gap, `hh_W` 5 hari, debounce marker, warna VR, aturan seri warna dominan, setiap revisi fase, dan catatan sekunder (37 test).

`tests/test_broker_daily.py` (tahap 2, 13 test) menguji penyimpanan dan backfill dengan HTTP palsu dan database sementara, jadi tidak memakai kuota: data ok tidak diambil dua kali, `empty` tidak diambil ulang, batas 3 kali coba untuk `error`, respons untuk tanggal lain ditolak, hari ini diabaikan sampai 17:00 WIB, urutan terbaru dulu, batas `max_requests`, berhenti tepat di cadangan kuota, dan data tersimpan bisa langsung dipakai `build_lpm`. `tests/test_lpm_service.py` (tahap 3, 23 test) menguji service, status job, dan ketiga route lewat Flask test client: tanpa histori = 0 request, sinkron maksimal 5 hari terbaru, tidak sinkron saat backfill berjalan, hari volume 0 dilewati, klaim job eksklusif, job mati terdeteksi, berhenti di cadangan kuota, 401/404/400/409.

Jalankan semua test (77 test): `python -m unittest discover -s tests -t .`

**Smoke test nyata tahap 3 (2026-10-21, `scratch/smoke_lpm_backfill.py`):** backfill BBCA dengan `max_requests=10` → 10 request, 10 hari `ok` (7–20 Okt), berhenti `max_requests`. Kuota 5 → 15, dan `get_lpm` sesudahnya 0 request. Pressure harian BBCA berkisar −0,07 sampai +0,40 (±4 sampai 40 poin), sehingga θ adaptif = 8,3 (5H) dan 4,1 (20H). Hari turun tajam 16 Okt (−15%) justru bertekanan beli +0,35.

Uji manual setelah backend jadi: buka modal untuk 1 saham likuid (BBCA) dan 1 saham kurang likuid, cek angka `pressure` 2–3 hari secara manual dari JSON broker mentah.

---

## 9. Urutan Pengerjaan

1. **Langkah 0**: verifikasi API (bagian 3.3), catat hasil di bagian 12. Kalau gagal, hentikan.
2. `screener/lpm.py` + `tests/test_lpm.py`, sampai semua test lulus.
3. Tabel `broker_daily` + `get_broker_daily` + `backfill_broker_daily` (dengan cadangan kuota).
4. Tiga route Flask + thread backfill + status.
5. Tab UI + chart + semua state.
6. Uji manual 2 saham, perbaiki, lalu perbarui `ProjectOverview/PROJECT_OVERVIEW.md` (tambahkan fitur ke daftar).
7. Commit terpisah per langkah besar (konvensi repo: `feat(lpm): ...`).

Urutan di atas adalah **Fase A**. Fase B (LPM Radar) dan Fase C (konfluensi) ada di bagian 13 dan baru dimulai setelah Fase A selesai dan dikalibrasi.

---

## 10. Kriteria Selesai

- [x] Langkah 0 terdokumentasi di bagian 12.
- [x] Semua test `tests/test_lpm.py` lulus (37 test, 2026-10-21).
- [x] Membuka tab LPM untuk saham yang historinya sudah lengkap **tidak memakai kuota** (kecuali hari baru). Terverifikasi di browser: BBCA 1 request (sinkron 21 Okt), TLKM tanpa histori 0 request.
- [x] Backfill berhenti saat sisa kuota menyentuh 200 (test) dan pesannya terlihat di UI (state kuota rendah diuji di browser dengan kuota disimulasikan).
- [x] Chart tersinkron (native pane; sekarang 2 panel: harga + LPM, lalu lensa), toggle Intensity/Vol Rotation berfungsi. Marker divergensi belum terlihat dengan data nyata karena BBCA baru 11 hari (`DATA_KURANG` tidak memunculkan marker); jalurnya diuji di test Python.
- [x] Semua state (loading, kosong, data kurang, kuota habis, error, progress backfill) tampil benar di desktop dan 375px.
- [x] Semua teks UI berbahasa Indonesia; disclaimer & keterbatasan selalu tampil.
- [x] Tidak ada API key baru yang di-hard-code.
- [x] Backfill penuh dijalankan dari tombol UI dengan API asli (2026-10-22): BBCA 69 request, 69 `ok`, coverage 80/80 tanpa gap, kuota hari itu 3 → 72. Progress bar dan pembaruan garis di tengah proses berfungsi; tombol tersembunyi selama berjalan dan hilang setelah lengkap. Marker divergensi nyata tampil (POSITIVE 14 Agu, 24 Agu, 10 Sep).

---

## 11. Risiko & Catatan

- **Histori API mungkin terbatas.** Kalau API hanya menyimpan beberapa bulan, `history_days` disesuaikan dan dicatat.
- **Pasar negosiasi (NG).** Kalau API tidak bisa memisahkan board RG/NG, LPM membaca semua board. Tulis keterbatasan ini apa adanya di UI.
- **Saham sangat tidak likuid.** `F_d` kecil membuat `A_d` tidak stabil. Kalau `F_d < 50`, tandai hari itu `low_liquidity: true` dan kalikan `pressure` dengan `F_d / 50` supaya satu order tidak mendominasi garis.
- **Temuan kalibrasi pertama (BBCA, 80 hari s/d 2026-10-21):** pressure positif di 57 dari 80 hari, rata-rata +8,9 poin/hari (min −12,5, maks +39,9), sehingga LPM naik terus ke ±715 sementara harga turun 5.550 → 5.275. Hasilnya: tren `RISING`, divergensi `POSITIVE`, fase `SENYAP`. Broker teratas MG, KZ, AK, ZP, YU.
- **Uji bias tahap 5 (2026-10-22, `scratch/calibrate_lpm.py`, 160 request):** backfill 80 hari untuk PTBA (saham naik, +35,8% dalam 80 hari) dan ASRM (tidak likuid, ±Rp20 juta/hari), lalu dibandingkan dengan BBCA. Semua 80/80 hari, tanpa gap.

| Saham | Harga 80H | Rata-rata pressure (poin) | Hari positif | Porsi smart beli / jual | Korelasi vs return hari sama | Korelasi vs return 5H ke depan | Tren / divergensi / fase |
|---|---|---|---|---|---|---|---|
| BBCA | −5,0% | +8,93 | 57/80 | 0,160 / 0,071 | −0,57 | −0,01 | RISING / POSITIVE / Senyap |
| PTBA | +35,8% | +2,24 | 51/80 | 0,078 / 0,056 | −0,34 | −0,15 | RISING / POSITIVE / Senyap |
| ASRM | −1,6% | +1,92 (median +0,22) | 41/80 | 0,122 / 0,084 | −0,24 | −0,05 | FLAT / POSITIVE / Senyap |

  Kesimpulan sementara (3 saham × 80 hari, semuanya di pasar yang sedang turun, jadi sampelnya kecil):
  1. **Bias positif konsisten.** Rata-rata pressure positif di ketiga saham, dan porsi smart beli selalu lebih besar dari porsi smart jual. Ketiganya berakhir di fase Senyap.
  2. **Pressure tinggi muncul di hari harga turun** (korelasi hari sama −0,24 sampai −0,57), konsisten di semua saham.
  3. **Belum ada daya prediksi** dalam sampel ini: korelasi dengan return 5 hari ke depan −0,15 sampai −0,01.
  4. **Mekanisme yang paling mungkin:** setiap transaksi dicatat dengan nilai yang sama di sisi beli dan sisi jual, jadi rata-rata per transaksi seorang broker hanya berbeda dari rata-rata pasar kalau transaksi besarnya **terkonsentrasi** di broker itu sementara lawannya **tersebar** di banyak broker. Di hari turun, penjual ritel tersebar dan pembeli besar terkonsentrasi, sehingga pressure positif. Artinya rumus sekarang lebih tepat dibaca sebagai **pendeteksi penyerapan (absorption)** daripada arah smart money murni. Itu informasi yang sah, tetapi belum terbukti mendahului harga.
  5. **Koreksi kandidat perbaikan sebelumnya:** "hitung `A_d` per sisi" tidak akan berpengaruh. Karena Σ`bval` = Σ`sval` dan Σ`bfrq` = Σ`sfrq` (bagian 12), rata-rata per sisi selalu sama dengan `A_d`.
  6. **ASRM:** 38 dari 80 hari kena `low_liquidity` (`F_d` < 50), dan nilai smart broker hanya ratusan ribu sampai jutaan Rupiah. Untuk saham setipis ini, LPM terutama mencerminkan beberapa transaksi per hari.

  **Tindak lanjut (2026-10-22):** (a) tab LPM diberi pemberitahuan "Eksperimental" di atas panel (selalu tampil); (b) uji varian di bawah; (c) validasi lebih luas belum dikerjakan.

- **Uji varian rumus (2026-10-22, `scratch/lpm_variants.py`, 0 request).** Semua koreksi out-of-sample: hari t hanya memakai 60 hari sebelumnya (minimal 20), sehingga yang dievaluasi 59 hari per saham (29 Jul – 21 Okt). `c_*` = korelasi Pearson; `slope5` = rata-rata pressure 5 hari (nilai yang dipakai klasifikasi tren).

| Varian | Rumus hari t | Hari positif (3 saham) | Korelasi vs return hari sama | vs return 5H ke depan | slope5 vs return 5H | slope5 vs return 10H |
|---|---|---|---|---|---|---|
| V0 raw | `p_t` | 106/177 (60%) | −0,37 | −0,14 | −0,21 | −0,06 |
| V1 detrend | `p_t − mean(p, 60H sebelumnya)` | 91/177 (51%) | −0,36 | −0,13 | −0,21 | −0,07 |
| V2 netral | `p_t − b·ret_t` | 125/177 (71%) | **+0,36** | −0,14 | −0,09 | −0,06 |
| V3 keduanya | `p_t − (a + b·ret_t)` | 90/177 (51%) | **+0,36** | −0,14 | −0,09 | −0,05 |

  Per saham, rata-rata pressure V0 → V1: BBCA +9,53 → +2,94, PTBA +1,81 → −0,85, ASRM +3,46 → +3,12. Status akhir V1: BBCA RISING/POSITIVE, PTBA FLAT/NONE, ASRM FLAT/POSITIVE (V0: ketiganya POSITIVE).

  Kesimpulan:
  1. **Detrend (V1) menghilangkan sebagian besar bias level** (hari positif 60% → 51%, BBCA dan PTBA turun mendekati 0), tanpa mengubah korelasi. Ia tidak merusak apa pun, tetapi juga tidak menambah daya prediksi. Kekurangannya: akumulasi yang konsisten selama berbulan-bulan ikut terhapus, padahal itu justru yang ingin ditangkap konsep LPM.
  2. **Netralisasi return (V2/V3) mengoreksi berlebihan.** Korelasi hari sama berbalik dari −0,37 ke +0,36, artinya koefisien `b` dari 60 hari sebelumnya tidak stabil saat diterapkan ke hari berikutnya. Dengan histori sependek ini, varian ini tidak bisa dipercaya.
  3. **Tidak ada varian yang menunjukkan daya prediksi.** Korelasi dengan return ke depan berkisar −0,21 sampai −0,05 di semua varian. Dengan 59 hari per saham dan jendela return yang tumpang tindih, angka sebesar ini masih dalam batas noise. Data ini tidak membuktikan LPM berguna, tetapi juga tidak membuktikan sebaliknya.
  4. **Rumus produksi belum diubah.** Mengganti rumus berdasarkan 3 saham × 59 hari berisiko mengejar noise.

  **Rekomendasi berikutnya:** tambah sampel sebelum mengubah rumus, misalnya 8–10 saham likuid dari sektor berbeda dengan histori 240 hari (±240 request per saham, total ±2.000–2.400 request, sekitar 3 hari kuota dengan cadangan 200). Ulangi tabel ini dengan uji yang tidak tumpang tindih (return 5 hari ke depan per blok 5 hari), lalu baru putuskan antara V0 dan V1.
- **Tuning parameter.** `R0`, `R1`, `θ` adalah titik awal. Setelah fitur jalan, bandingkan garis LPM dengan pergerakan harga 20–60 hari ke depan di beberapa saham sebelum mengubahnya, dan catat perubahannya di sini.
- **Keamanan (di luar cakupan, tapi perlu ditangani):** API key IDX Edge PRO saat ini tertulis langsung di `screener/idx_api_client.py` dan `ProjectOverview/APISpecs.md`, dan keduanya ter-commit ke git. Sebaiknya dipindah ke `.env` (`IDX_EDGE_API_KEY`) dan key-nya diganti, sebagai tugas terpisah. Fitur LPM cukup memakai `IDXApiClient` yang sudah ada.

---

## 12. Hasil Verifikasi API (diisi saat Langkah 0)

Diuji 2026-10-21 dengan `scratch/verify_broker_daily.py`, **5 request** (kuota 0 → 5). Respons mentah tersimpan di `scratch/lpm_fixtures/` (R1–R5 + `summary.json`) dan dipakai sebagai fixture test.

| # | Request | Saham / tanggal |
|---|---|---|
| R1 | satu hari | BBCA, 2026-10-20 |
| R2 | rentang 3 hari bursa | BBCA, 2026-10-16 s/d 2026-10-20 |
| R3 | satu hari, ±6 bulan lalu | BBCA, 2026-04-20 |
| R4 | satu hari, ±12 bulan lalu | BBCA, 2025-10-20 |
| R5 | satu hari, saham tidak likuid | ASRM (turnover rata-rata 20 hari ±Rp18 juta), 2026-10-20 |

| Pertanyaan | Hasil |
|---|---|
| Single-day `start_date = end_date` mengembalikan data hari itu saja? | **Ya.** `broker_start_date = broker_end_date = 2026-10-20`, dan Σ`bvol` = 1.131.013.100 lembar, **sama persis** dengan volume yfinance hari itu. Sama persis juga untuk R3, R4, dan R5. **LPM harian bisa dibangun dengan endpoint ini.** |
| Rentang multi-hari = agregat atau per hari? | **Agregat.** R2 hanya punya satu daftar broker. Σ`bvol` R2 = 2.755.035.700 = jumlah persis volume yfinance 16 + 19 + 20 Okt. Rincian per hari tidak ada, jadi tetap 1 request per hari bursa. |
| Histori paling lama yang tersedia | **Sejak 2020.** `broker_date_min` = 2020-01-02 (BBCA) dan 2020-01-09 (ASRM). R4 (12 bulan lalu) lengkap dengan 84 broker. Histori tidak membatasi `history_days`. |
| `bfrq`/`sfrq` selalu terisi? | **Ya**, tidak ada yang null, termasuk ASRM (10 broker, 35 transaksi). `frq = 0` hanya muncul kalau nilai sisi itu juga 0. |
| Ada parameter board (RG/NG)? | **Tidak.** Tidak ada field atau kunci board di respons. Volume broker summary sama persis dengan volume yfinance, jadi cakupan board keduanya sama. Apakah itu hanya RG atau semua board tidak bisa dipastikan dari data ini. |

**Temuan tambahan dan dampaknya ke spesifikasi:**

1. **Nama field berbeda dari `APISpecs.md`.** Kunci tingkat atas: `stock_code`, `flow`, `broker_start_date`, `broker_end_date`, `broker_date_min`, `broker_date_max`, `broker_net`, `brokers`, `broker_levels`. Tidak ada `latest_date`, `broker_start`, atau `broker_end` di respons yang memakai tanggal. Validasi sebelum menyimpan: `broker_start_date == broker_end_date == tanggal yang diminta`.
2. **Field broker:** `broker_code`, `broker_name`, `bval`, `bvol`, `bfrq`, `sval`, `svol`, `sfrq`, `nval`, `nvol`. Volume dalam **lembar**, bukan lot. `nval = bval − sval` di semua baris.
3. **`frq` menghitung transaksi (match), bukan order.** Di kelima respons Σ`bfrq` = Σ`sfrq` persis (BBCA 20 Okt: 165.196 = 165.196). Ini hanya mungkin kalau tiap transaksi dihitung sekali di sisi beli dan sekali di sisi jual. Akibatnya `val/frq` adalah nilai rata-rata per **transaksi**, yang ikut terseret ke ukuran lawan transaksi. Ini keterbatasan tambahan yang perlu ditulis di UI.
4. **Σ`bval` = Σ`sval` persis**, jadi `T_d = Σbval`.
5. **`broker_levels`** berisi daftar pembeli dan penjual yang dipasangkan per peringkat (dengan `bavg`/`savg`), **bukan level harga**. LPM tidak memakainya. Yang disimpan di `broker_daily` hanya `brokers`.
6. **Ukuran:** ±30–40 KB per respons BBCA (`all_data=true`), ±4 KB untuk ASRM. Dengan hanya menyimpan `brokers` dan field yang dipakai, perkiraannya ±15 KB per saham per hari.
7. **Belum diuji:** perilaku API untuk tanggal libur. Mitigasinya validasi di poin 1, ditambah tanggal yang diminta selalu berasal dari kalender yfinance.

**Rumus bagian 4 pada data nyata** (dihitung dari fixture, tanpa request tambahan):

| Hari | `F_d` | `A_d` | `pressure` | `100 × pressure` | `E_d` | `C_top5` | Batas atas `Int` (≈ 1/C) |
|---|---|---|---|---|---|---|---|
| BBCA 2026-10-20 | 330.392 | Rp34,0 jt | +0,159 | +15,9 | 0,19 | 0,39 | ±2,5 |
| BBCA 2026-04-20 | 70.280 | Rp25,4 jt | +0,109 | +10,9 | 0,48 | 0,40 | ±2,5 |
| BBCA 2025-10-20 | 174.992 | Rp35,4 jt | −0,067 | −6,7 | 0,56 | 0,49 | ±2,0 |
| ASRM 2026-10-20 | 70 | Rp0,1 jt | −0,018 | −1,8 | 0,50 | 0,86 | ±1,2 |

Ini baru 4 sampel, tapi sudah menguatkan dua catatan tinjauan:
- **θ = 0,5 poin/hari jauh di bawah besaran harian** (±7–16 poin pada BBCA), jadi θ perlu adaptif atau dikalibrasi (pertanyaan 3).
- **Rasio Intensity punya batas atas yang terlalu rendah.** Top-5 BBCA sudah memegang 39–49% transaksi, jadi `SPIKE_EKSTREM` (≥ 2,5) praktis mustahil. Di ASRM batasnya ±1,2, jadi `SPIKE` (≥ 1,5) pun mustahil (pertanyaan 4).

ASRM (`F_d` = 70) hanya sedikit di atas ambang `low_liquidity` (`F_d < 50`, bagian 11).

---

## 13. Peta Jalan: LPM sebagai Lensa Konfirmasi

> **Keputusan user (2026-10-21):** LPM **tidak** dijadikan screener ke-5 yang berdiri sendiri. Empat screener yang ada (SEPA, RSI Divergence, Pre-Breakout, Quality Setup) menjawab *saham mana yang menarik secara teknikal*. LPM menjawab pertanyaan berikutnya: *dari kandidat itu, mana yang sedang dikumpulkan smart money?*
>
> Screener LPM untuk seluruh 941 saham **tidak mungkin**: pembaruan hariannya saja 941 request, di atas kuota 1.000/hari dikurangi cadangan 200.

Dikerjakan berurutan. Fase berikutnya baru dimulai setelah fase sebelumnya selesai.

### 13.1 Fase A: tab LPM on-demand (bagian 1–12 dokumen ini)
Sesuai spesifikasi di atas, mulai dari Langkah 0. Fase A wajib selesai **dan dikalibrasi** dulu (`θ`, `R0`/`R1`, aturan fase dicocokkan dengan data nyata, bagian 11 "Tuning parameter"), karena Fase B dan C memakai rumus yang sama. Screener yang dibangun di atas rumus yang belum dikalibrasi akan menyesatkan.

### 13.2 Fase B: view "LPM Radar" (universe terbatas)

**Universe** (gabungan, tanpa duplikat), dibaca dari cache hasil scan yang sudah ada:
| Sumber | Syarat | File |
|---|---|---|
| SEPA Trend | `status == "CONFIRMED"` | `data/cache/scan_result.json` |
| Pre-Breakout | `status == "READY"` | `data/cache/pre_breakout_result.json` |
| Quality Setup | `grade == "Elite"` | `data/cache/quality_setup_result.json` |
| RSI Divergence 1D | divergensi segar (`bars_ago ≤ 5`) | `data/cache/rsi_div_1d.json` |
| Watchlist | semua yang di-pin | `get_watchlist_tickers()` di `screener/journal_db.py` |

Perkiraan ukuran: 30–50 saham.

**Dua tingkat histori** (memakai tabel `broker_daily` yang sama dengan Fase A):
- Radar: `LPM_PARAMS["radar_history_days"] = 25` hari bursa. Cukup untuk `slope_20`, tren, dan divergensi.
- Modal: histori penuh (`history_days`) diambil saat tab LPM dibuka, untuk Intensity, Vol Rotation, dan Fase.
- Karena warm-up Intensity/VR belum terpenuhi dengan 25 hari, kolom Fase di Radar tampil `—` sampai histori saham itu cukup.

**Job harian:**
- Skrip terpisah `deploy/run_lpm_radar.py`, cron **18:30 WIB** hari bursa (sesudah `run_scan.py` jam 18:00), supaya kegagalan satu job tidak mengganggu yang lain.
- Bisa juga dipicu manual lewat `POST /api/scan/lpm-radar` (pola sama dengan Quality Setup).
- Anggaran: `LPM_PARAMS["radar_daily_budget"] = 300` request/hari. Cadangan global (sisa kuota < 200 → berhenti) tetap berlaku.
- Urutan prioritas dalam anggaran:
  1. Pembaruan 1 hari terbaru untuk anggota Radar yang sudah punya histori (1 request/saham).
  2. Backfill anggota baru, mulai dari saham yang muncul di lebih dari satu screener. Kalau anggaran habis, sisanya dilanjutkan hari berikutnya.
- Saham yang sudah 10 hari bursa tidak lolos screener mana pun (dan tidak di-pin) berhenti diperbarui. Datanya di `broker_daily` tetap disimpan.

**Penyimpanan hasil:** `data/cache/lpm_radar.json` (pola sama dengan cache screener lain), berisi per saham: `ticker`, `as_of`, `trend`, `slope_5`, `slope_20`, `divergence`, `phase` (atau `null`), `history_days`, `sources` (daftar screener asal).

**API** (semua `@admin_required`):
| Route | Isi |
|---|---|
| `GET /api/lpm-radar` | Isi `lpm_radar.json`. Tidak memakai kuota. |
| `POST /api/scan/lpm-radar` | Memicu job Radar di background. |
| `GET /api/status/lpm-radar` | Progres job dan request yang terpakai hari ini. |

State job disimpan di SQLite, bukan di dict proses, karena Gunicorn berjalan dengan 3 worker.

**UI:**
- Menu baru di sidebar + `templates/views/view_lpm_radar.html` + `static/js/screeners/lpm_radar.js`.
- Kolom: Ticker, Sumber (badge screener asal), Tren LPM, Slope 20H, Divergensi, Fase, Histori (`25/25`).
- Klik baris membuka halaman LPM untuk saham itu (`openLpmPage(ticker)`).

**Perubahan aturan proyek:** `PROJECT_OVERVIEW.md` bagian 5 poin 3 saat ini melarang batch call ke IDX Edge PRO di background. Saat Fase B selesai, aturan itu diperbarui menjadi: *batch ke IDX Edge PRO hanya boleh lewat job LPM Radar, dengan anggaran harian tetap. Screener lain tetap hanya memakai Yahoo Finance.*

**Perkiraan kuota (40 saham):**
| | Request |
|---|---|
| Backfill awal 40 × 25 hari | 1.000 (selesai ±3–4 hari dengan anggaran 300/hari) |
| Pembaruan harian | 40/hari |
| Anggota baru ±5/hari × 25 | ±125/hari |
| **Rutin per hari** | **±165** |

### 13.3 Fase C: konfluensi di screener yang sudah ada

- Badge LPM kecil di tabel SEPA, Pre-Breakout, Quality Setup, dan RSI Divergence. Frontend memuat `GET /api/lpm-radar` sekali lalu memetakan per ticker. **Tidak ada request API tambahan.**
- Saham tanpa data Radar tidak diberi badge (bukan "Netral").
- Label konfluensi:

| Kombinasi | Label | Makna |
|---|---|---|
| Pre-Breakout `READY` + fase `PERSIAPAN` / `SENYAP` | Timing Terkuat | Setup teknikal didukung akumulasi |
| SEPA `CONFIRMED` + LPM `RISING` | Tren Didukung Dana | Tren naik sejalan aliran smart money |
| Quality `Elite` + divergensi `NEGATIVE` | Waspada Distribusi | Harga bagus, barang sedang dilepas |
| RSI Bullish Div + divergensi `POSITIVE` | Pembalikan Didukung | Pembalikan disertai akumulasi senyap |

- Filter opsional "Hanya konfluensi LPM" di tiap tabel.
- **Validasi:** setelah data Radar terkumpul ≥ 40 hari bursa, uji tiap label di Backtest Lab (return 20 dan 60 hari ke depan dibanding saham tanpa label). Hasilnya dicatat di bagian 11 sebelum label diubah atau ditambah.

### 13.4 Kriteria selesai Fase B & C
- [ ] Job Radar tidak pernah melewati `radar_daily_budget` dan berhenti saat sisa kuota < 200.
- [ ] Backfill yang terpotong anggaran dilanjutkan otomatis di hari berikutnya.
- [ ] `GET /api/lpm-radar` dan badge konfluensi tidak memakai kuota.
- [ ] Klik baris Radar membuka halaman LPM untuk saham itu.
- [ ] `PROJECT_OVERVIEW.md` diperbarui (aturan batch + fitur baru).

---

## 14. Pertanyaan Terbuka (dijawab sebelum tahap terkait)

Dari tinjauan spesifikasi 2026-10-21. Jawaban dicatat di sini, lalu bagian terkait di atas diperbarui.

**Sebelum Langkah 0**
1. ~~Saham tidak likuid untuk uji R5?~~ Dijawab: dipilihkan, ASRM.
2. ~~Boleh respons mentah Langkah 0 disimpan di `scratch/` sebagai fixture test?~~ Dijawab: boleh, ada di `scratch/lpm_fixtures/`.

**Sebelum `screener/lpm.py`**
Pertanyaan 3–8 dijawab 2026-10-21: semua usulan dipakai.

3. ~~`θ` adaptif atau tetap?~~ **Adaptif**: `max(0,5, k × σ / √n)`, k = 1 (bagian 4.5).
4. ~~Intensity z-score/persentil?~~ **z-score** terhadap 20 hari sebelumnya (bagian 4.7).
5. ~~Histori 80 atau 60 hari?~~ **80 hari** (bagian 5.4).
6. ~~Revisi aturan fase?~~ **Diterapkan** (bagian 4.6 dan 4.9).
7. ~~Data hari ini?~~ **Diabaikan sampai 17:00 WIB** (bagian 5.3).
8. ~~Berapa hari diambil langsung?~~ **Maksimal 5** (bagian 6).

**Sebelum route & UI** — dijawab 2026-10-22: semua rekomendasi dipakai.

9. ~~Tab Bandar ikut menulis `broker_daily`?~~ **Ya.** `get_broker_summary` (flow `all`) menyimpan responsnya sebagai hari LPM kalau `broker_start_date = broker_end_date`, hari itu sudah final, dan belum tersimpan (`_store_latest_broker_day`). Catatan: belum dipastikan apakah respons tanpa tanggal memuat `broker_start_date`; kalau tidak, tidak ada yang disimpan (aman).
10. ~~v4.2.0 atau v5?~~ **v5.2.1** dengan native pane (bagian 7).
11. ~~Warna Intensity?~~ **Token biru yang sudah ada** (`--status-div-hid-text`).
12. ~~Refresh?~~ **Hitung ulang dari data tersimpan** (+ sinkron hari baru sesuai aturan maksimal 5).
13. ~~Pembeli dan penjual?~~ **Ya**, diurutkan berdasarkan |net|, ditampilkan "Beli"/"Jual".
14. ~~Desktop-only atau mobile?~~ **Layout mobile yang sudah ada berlaku**; `.agent/Design.md` bagian 12 sudah usang.
