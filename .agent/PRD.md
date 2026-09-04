# PRD — IDX SEPA Trend Screener
**Product Requirements Document**
**Versi**: 1.0
**Tanggal**: 2026-09-01
**Status**: Draft

---

## 1. Ringkasan Produk

**IDX SEPA Trend Screener** adalah aplikasi web lokal yang melakukan screening seluruh saham di Bursa Efek Indonesia (IDX) berdasarkan **SEPA Trend Template** milik Mark Minervini. Aplikasi ini mengatasi keterbatasan TradingView yang hanya mampu memproses maksimal 15 ticker secara bersamaan, dengan kemampuan scan **~900+ saham IDX** sekaligus.

### Tujuan
- Mengidentifikasi saham IDX yang memenuhi kriteria **Stage 2 CONFIRMED** dan **WATCHLIST** berdasarkan 8 kriteria SEPA Trend Template
- Memberikan trader/investor daftar saham prioritas yang sudah terfilter secara sistematis dan kuantitatif
- Menyajikan hasil dalam antarmuka yang bersih, cepat, dan mudah dibaca

---

## 2. Latar Belakang

Mark Minervini mengembangkan **SEPA (Specific Entry Point Analysis) Trend Template** sebagai framework untuk mengidentifikasi saham yang berada dalam **Stage 2 Uptrend**. Saham dalam kondisi ini secara historis memiliki risk/reward terbaik untuk entry posisi beli.

Di TradingView, sudah tersedia Pine Script indicator & screener SEPA, namun dibatasi hanya **15 ticker per screener**. Dengan ~900 saham aktif di IDX, dibutuhkan tool terpisah yang mampu scan seluruh universe saham IDX secara otomatis.

---

## 3. Target Pengguna

- **Trader / Investor Saham IDX** yang menggunakan metodologi Minervini / growth trading
- Pengguna yang sudah familiar dengan konsep Stage Analysis dan SEPA Trend Template
- Pengguna yang ingin daftar watchlist saham IDX terfilter secara kuantitatif setiap harinya

---

## 4. Fitur Utama (Scope v1.0)

### 4.1 Screening Engine
- Scan seluruh saham IDX berdasarkan daftar ticker dari file CSV master (`idx_tickers.csv`)
- Fetch data harga historis harian via **yfinance** (Yahoo Finance, format ticker: `XXXX.JK`)
- Hitung 8 kriteria SEPA Trend Template untuk setiap saham
- Hitung RS Rating (0–100) vs benchmark IHSG (`^JKSE`)
- Kategorikan hasil: **CONFIRMED** (score = 8/8) atau **WATCHLIST** (score >= 6/8)
- Saham dengan score < 6 **tidak ditampilkan** (hidden)

### 4.2 Delapan (8) Kriteria SEPA Trend Template

| No | Kriteria | Parameter Default |
|----|----------|-------------------|
| C1 | Harga saat ini > MA150 **dan** MA200 | SMA 150, SMA 200 |
| C2 | MA150 > MA200 | — |
| C3 | MA200 sedang uptrend (slope naik) | Min 1 bulan (22 hari trading) |
| C4 | MA50 > MA150 **dan** MA200 | SMA 50 |
| C5 | Harga saat ini > MA50 | — |
| C6 | Harga >= 25% di atas 52-Week Low | Default: 25% |
| C7 | Harga dalam jarak <= 25% dari 52-Week High | Default: 25% |
| C8 | RS Rating >= 70 (relatif terhadap IHSG) | Default threshold: 70 |

**RS Rating Formula (IBD Weighted)**:
```
stock_perf = 0.40 x r_3m + 0.20 x r_6m + 0.20 x r_9m + 0.20 x r_12m
rs_relative = (1 + stock_perf) / (1 + bench_perf)
rs_score    = percentile_rank(rs_relative, lookback=252) x 100
```

### 4.3 Antarmuka Pengguna (UI)
- **Mode**: On-demand — user klik tombol "Scan Sekarang"
- **UX Scan**: Loading spinner selama proses scan berlangsung
- **Tema UI**: Enterprise Clear dengan aksen **Green Lime** (`#84cc16`)
- **Font**: Inter (Google Fonts)

### 4.4 Tabel Hasil
Kolom yang ditampilkan:

| Kolom | Keterangan |
|-------|------------|
| Ticker | Kode saham IDX (tanpa suffix `.JK`) |
| Nama Perusahaan | Nama lengkap emiten |
| Sektor | Sektor industri |
| Harga | Harga penutupan terakhir (IDR) |
| SEPA Score | Skor terpenuhi dari total 8 kriteria (x/8) |
| Status | Badge: **CONFIRMED** (hijau) / **WATCHLIST** (amber) |
| Kriteria (C1-C8) | 8 Mini Pill Badges [1] s/d [8] (hijau/abu) dengan hover tooltip detail |
| RS Rating | Skor 0–100 vs IHSG |
| % 52W Low | Jarak harga dari 52-Week Low (%) |
| Link Chart | Tombol link langsung ke TradingView chart |

### 4.5 Filter
- **Slider minimum score**: Filter tampilan tabel berdasarkan minimum SEPA score (range 1–8, default: 6)
- Filter bekerja **real-time** tanpa reload halaman

### 4.6 Caching
- Hasil scan disimpan ke file **JSON cache** (`data/cache/scan_result.json`)
- Saat aplikasi dibuka kembali, hasil cache langsung dimuat tanpa perlu scan ulang
- Informasi **timestamp scan terakhir** ditampilkan di UI
- User dapat trigger scan baru kapan saja

---

## 5. Arsitektur Teknis

### Stack
| Layer | Teknologi |
|-------|-----------|
| Backend | **Python 3.10+**, **Flask 3.x** |
| Data Fetching | **yfinance** |
| Data Processing | **pandas**, **numpy** |
| Frontend | **Vanilla HTML5 + CSS3 + JavaScript (ES6+)** |
| Font | Google Fonts — Inter |
| Cache | File JSON lokal |

### Struktur Folder
```
d:\Learning\SepaTrend\
├── app.py                        # Flask server — API endpoints
├── requirements.txt              # Python dependencies
├── screener/
│   ├── __init__.py
│   ├── calculator.py             # Engine kalkulasi 8 kriteria SEPA
│   ├── data_fetcher.py           # Fetch data via yfinance
│   └── rs_calculator.py         # Kalkulasi RS Rating vs IHSG
├── data/
│   ├── idx_tickers.csv           # Master list ticker IDX (ticker, nama, sektor)
│   └── cache/
│       └── scan_result.json      # Cache hasil scan terakhir
├── static/
│   ├── css/
│   │   └── style.css             # Enterprise Green Lime theme
│   └── js/
│       └── app.js                # Frontend logic
└── templates/
    └── index.html                # Main UI page
```

### API Endpoints (Flask)
| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| `GET` | `/` | Serve halaman utama `index.html` |
| `POST` | `/api/scan` | Trigger scan seluruh ticker IDX |
| `GET` | `/api/results` | Ambil hasil cache scan terakhir |
| `GET` | `/api/status` | Cek status (apakah sedang scanning) |

---

## 6. Data Source

### Ticker List
- File: `data/idx_tickers.csv`
- Format: `ticker, name, sector`
- Contoh: `BBCA, Bank Central Asia Tbk, Keuangan`
- Di-maintain manual, diawali konstituen LQ45/IDX80/IDX Composite

### Harga Historis
- Provider: **Yahoo Finance** via `yfinance`
- Suffix ticker: `.JK` (contoh: `BBCA.JK`)
- Periode: **2 tahun** data harian (untuk memastikan cukup 252 bar)
- Benchmark: `^JKSE` (IHSG)

### Ketersediaan Data
- Saham dengan data < 252 hari trading dianggap **tidak cukup data** dan dilewati
- Error fetch (ticker tidak valid, delisted) diabaikan dan dilanjutkan ke ticker berikutnya

---

## 7. Kriteria Penerimaan (Acceptance Criteria)

| # | Skenario | Hasil yang Diharapkan |
|---|----------|-----------------------|
| 1 | User buka aplikasi | Hasil cache langsung tampil (jika ada), timestamp scan terakhir terlihat |
| 2 | User klik "Scan Sekarang" | Spinner muncul, proses berjalan di background |
| 3 | Scan selesai | Tabel hasil muncul, hanya CONFIRMED dan WATCHLIST yang ditampilkan |
| 4 | User geser slider ke 8 | Hanya saham Stage 2 CONFIRMED yang tampil |
| 5 | User geser slider ke 6 | CONFIRMED + WATCHLIST tampil |
| 6 | User klik link TradingView | Browser buka chart TradingView untuk ticker tersebut |
| 7 | Saham tidak cukup data | Dilewati, tidak tampil di hasil (tidak error) |
| 8 | Buka ulang browser | Cache dimuat, tidak perlu scan ulang |
| 9 | Hasil SEPA Score akurat | Divalidasi manual dengan TradingView indicator untuk 3–5 saham sampel |

---

## 8. Out of Scope (v1.0)

- Auto-refresh otomatis / real-time streaming data
- Notifikasi / alert via email atau Telegram
- Multi-user / authentication
- Deployment ke cloud / server publik
- Historical backtesting
- Chart embedded di dalam aplikasi
- Export ke Excel/PDF (dapat ditambahkan di v2.0)
- Filter berdasarkan sektor (dapat ditambahkan di v2.0)

---

## 9. Referensi

- **Indicator Template**: `ProjectOverview/Indicator Templatate Sepa Trend` — Pine Script v5
- **Screener Template**: `ProjectOverview/Screnner_SepaTrend` — Pine Script v5
- Buku: *Trade Like a Stock Market Wizard* — Mark Minervini
- yfinance docs: https://python-yfinance.readthedocs.io/
