# 📌 TIREXXZ SCRENNER — DOKUMENTASI LENGKAP & STATUS PROYEK
> **Handover Notes untuk Developer & Agent Masa Depan**  
> **Terakhir Diperbarui**: September 2026  
> **Status**: ✅ **Production-Ready (Feature-Complete, Tested & Ready to Deploy VPS)**

---

## 1. Ringkasan Eksekutif Proyek

**Tirexxz Screnner** (sebelumnya SEPA Trend Screener Pro) adalah platform analisa dan penyaring (*screener*) saham komprehensif untuk **Bursa Efek Indonesia (IDX)**. 

Aplikasi ini menggabungkan:
1. **Analisa Kuantitatif & Trend Template Mark Minervini (SEPA)**: Mengidentifikasi saham dalam Fase 2 (Stage 2 Uptrend).
2. **Pre-Breakout Setup (VCP)**: Mengidentifikasi saham yang sedang dalam konsolidasi harga ketat dengan volatilitas mengecil sebelum breakout resistance.
3. **RSI Bullish Divergence**: Mengidentifikasi potensi pembalikan arah harga (Regular & Hidden Bullish Divergence).
4. **Bandarmologi & Analisa Komprehensif On-Demand**: Terintegrasi langsung dengan API **IDX Edge PRO** (`https://stock.arjum.com`) untuk melacak pergerakan broker (*smart money*), tren akumulasi, laporan keuangan, dan rencana trading otomatis.
5. **Sistem Keamanan Administrator**: Full private screener dengan manajemen sesi terenkripsi, brute-force rate limiter, dan kredensial dinamis.
6. **Infrastruktur Produksi VPS**: Siap dideploy 24/7 di VPS Ubuntu menggunakan Gunicorn, Nginx Reverse Proxy, Systemd, dan Cron Auto-Scan jam 18:00 WIB.

---

## 2. Fitur-Fitur yang Sudah Selesai 100%

### A. Tiga Mesin Screener Utama
1. **SEPA Trend Screener ([screener/calculator.py](file:///d:/Learning/SepaTrend/screener/calculator.py))**:
   * Menilai 8 Kriteria SEPA Mark Minervini:
     * C1: Harga > MA150 & Harga > MA200
     * C2: MA150 > MA200
     * C3: Kemiringan MA200 Menanjak (Lookback Min 1 bulan / Ideal 4-5 bulan)
     * C4: MA50 > MA150 & MA50 > MA200
     * C5: Harga > MA50
     * C6: Harga >= 25% di atas 52-Week Low
     * C7: Harga <= 25% dari 52-Week High
     * C8: IBD RS Rating >= 70 (Percentile Rank vs IHSG `^JKSE` dengan pembobotan 40% 3M, 20% 6M, 20% 9M, 20% 12M).
   * Klasifikasi: **CONFIRMED** (Skor 8/8) vs **WATCHLIST** (Skor 6–7/8).

2. **Pre-Breakout Setup ([screener/pre_breakout.py](file:///d:/Learning/SepaTrend/screener/pre_breakout.py))**:
   * Filter likuiditas minimum (Turnover 20 hari >= Rp500 Juta).
   * Deteksi konsolidasi volatilitas mengecil (VCP/Tight Base).
   * Jarak ke Resistance terdekat (`dist_res_pct <= 5.0%`).
   * Relative Volume (RVOL) dan status kesiapan: **READY** (Skor >= 75) vs **FORMING** (Skor >= 60).

3. **RSI Bullish Divergence ([screener/rsi_divergence.py](file:///d:/Learning/SepaTrend/screener/rsi_divergence.py))**:
   * Swing low detection (order 5 bars) pada timeframe harian.
   * **Regular Bullish**: Price Lower Low + RSI Higher Low (sinyal potensi pembalikan arah).
   * **Hidden Bullish**: Price Higher Low + RSI Lower Low (sinyal kelanjutan tren naik).

---

### B. Integrasi On-Demand IDX Edge PRO API ([screener/idx_api_client.py](file:///d:/Learning/SepaTrend/screener/idx_api_client.py))
* **Proteksi Kuota 1.000 Req/Hari**:
  * Menggunakan database SQLite lokal ([data/cache/idx_api_cache.db](file:///d:/Learning/SepaTrend/data/cache/idx_api_cache.db)).
  * Cache otomatis per hari bursa (TTL 1 hari untuk broker flow/analisis, TTL 14 hari untuk laporan keuangan).
  * Pemanggilan API dilakukan secara **On-Demand** (hanya terpotong jika tombol "Cek Bandar" / Modal Detail dibuka), tidak ada batch call massal yang memboroskan kuota.
* **Fitur-Fitur Modal Saham**:
  * **Tab 1: Bandarmologi & Flow**:
    * Top 5 Net Buyers dan Top 5 Net Sellers (menggunakan query `all_data=true` untuk menarik 41+ broker lengkap).
    * Total turnover, total net volume, dan rasio konsentrasi Top 3 Broker.
    * Status Bandarmologi (`BIG_ACCUM`, `NORMAL_ACCUM`, `NEUTRAL`, `NORMAL_DIST`, `BIG_DIST`).
    * Tren Akumulasi Bandar (Grafik mini harian 7 hari bursa terakhir + label tren `UPTREND_ACCUM` / `DOWNTREND_DIST`).
  * **Tab 2: Laporan Keuangan**:
    * Kuartalan EPS & Laba Bersih historis.
    * Perhitungan YoY EPS Growth otomatis (Badge *SEPA Certified* jika growth >= +20%).
  * **Tab 3: Analisis Komprehensif AI**:
    * Sinyal & Skor AI (contoh: *Score 50/75 - Sinyal campuran*).
    * Rekomendasi Aksi Taktis (*WASPADA / ACCUMULATE / BUY*).
    * Panduan Posisi (*Jika belum punya*, *Jika sudah punya*).
    * Target 1, Target 2, dan Stop Loss dinamis.
    * Daily Pivots Level (*R2, R1, P, S1, S2*).

---

### C. Sistem Autentikasi & Keamanan ([screener/auth.py](file:///d:/Learning/SepaTrend/screener/auth.py))
* **Full Private Mode**: Seluruh rute dashboard (`/`) dan semua endpoint API (`/api/*`) wajib login admin via decorator `@admin_required`.
* **Kredensial Dinamis `.env`**:
  * Mengambil `ADMIN_USERNAME` dan `ADMIN_PASSWORD` dari file [`.env`](file:///d:/Learning/SepaTrend/.env).
  * Dibaca secara dinamis (real-time reload tanpa perlu restart server).
* **Session Management**:
  * Signed HMAC SHA-256 cookie session (`HttpOnly`, `SameSite=Lax`).
  * Durasi sesi default: 7 hari, atau 30 hari jika opsi *"Ingat Saya"* dicentang.
* **Proteksi Brute-Force**: Maksimal 5x kesalahan login per 15 menit per IP client.
* **Antarmuka Login**:
  * Desain *Enterprise Clear White & Emerald Green* ([templates/login.html](file:///d:/Learning/SepaTrend/templates/login.html), [static/css/login.css](file:///d:/Learning/SepaTrend/static/css/login.css)).
  * Clean card, eye toggle password, validasi AJAX instan, dan tombol tactile dengan spinner.
* **Sidebar Dashboard**:
  * Indikator status profil admin online dan tombol logout `[🚪]`.

---

### D. Paket Deployment VPS Produksi ([deploy/](file:///d:/Learning/SepaTrend/deploy/))
* **Stack**: Ubuntu 22.04/24.04 LTS, Gunicorn WSGI, Nginx Reverse Proxy, Linux Systemd.
* **1-Click Setup Script ([deploy/setup.sh](file:///d:/Learning/SepaTrend/deploy/setup.sh))**: Otomatis install paket, python venv, dependencies, setup `.env`, konfigurasi systemd & nginx.
* **Systemd Service ([deploy/tirexxz.service](file:///d:/Learning/SepaTrend/deploy/tirexxz.service))**: Daemon Gunicorn auto-restart 24/7.
* **Nginx Configuration ([deploy/nginx.conf](file:///d:/Learning/SepaTrend/deploy/nginx.conf))**: Reverse proxy port 5000, static files cache 30 hari, Gzip, security headers, dan template SSL Certbot.
* **Cron Auto-Scan ([deploy/run_scan.py](file:///d:/Learning/SepaTrend/deploy/run_scan.py) & [deploy/crontab.txt](file:///d:/Learning/SepaTrend/deploy/crontab.txt))**:
  * Skrip CLI mandiri yang mengevaluasi 205 saham IDX secara background tanpa membuka browser.
  * Teruji selesai berjalan hanya dalam tempo **~10 detik**.
  * Jadwal: Setiap **Senin – Jumat jam 18:00 WIB** (`0 18 * * 1-5`).
* **Panduan Deployment ([deploy/DEPLOYMENT_GUIDE.md](file:///d:/Learning/SepaTrend/deploy/DEPLOYMENT_GUIDE.md))**: Petunjuk lengkap dari awal SSH VPS sampai domain live ber-HTTPS.

---

## 3. Peta Struktur Direktori & File

```
SepaTrend/
│
├── app.py                          # Flask Web Application Core & API Routing
├── requirements.txt                # Dependensi Python (Flask, yfinance, pandas, numpy, requests, gunicorn)
├── .env                            # Kredensial aktif & Secret Key (JANGAN commit ke git publik)
├── .env.example                    # Template konfigurasi environment untuk server VPS
│
├── screener/                       # Modul Inti Logika & Screener
│   ├── auth.py                     # Autentikasi, verifikasi kredensial .env, rate limiter, decorator @admin_required
│   ├── calculator.py               # Evaluator SEPA Trend 8-Criteria (Minervini Stage 2)
│   ├── data_fetcher.py             # Fetch data historis Yahoo Finance (.dropna proteksi NaN)
│   ├── rs_calculator.py            # Perhitungan IBD RS Rating vs IHSG (^JKSE)
│   ├── pre_breakout.py             # Evaluator Pre-Breakout Setup & VCP
│   ├── rsi_divergence.py           # Evaluator RSI Bullish Divergence (Regular & Hidden)
│   └── idx_api_client.py           # Client IDX Edge PRO API + SQLite caching & quota tracker
│
├── templates/                      # Template HTML Jinja2
│   ├── index.html                  # Halaman utama aplikasi (Dashboard Shell)
│   ├── login.html                  # Halaman login enterprise (Clear White & Emerald Green)
│   ├── components/
│   │   └── sidebar.html            # Sidebar navigasi, live quota widget, status admin, tombol logout
│   ├── views/
│   │   ├── view_sepa.html          # Tampilan tabel SEPA Trend
│   │   ├── view_rsi.html           # Tampilan tabel RSI Divergence
│   │   └── view_prebreakout.html   # Tampilan tabel Pre-Breakout
│   └── modals/
│       ├── modal_stock_detail.html # Modal 3 Tab (Bandarmologi, Financials, AI Analysis)
│       ├── modal_sepa.html         # Modal detail kriteria SEPA per emiten
│       ├── modal_prebreakout.html  # Modal detail setup breakout per emiten
│       ├── modal_rsi.html          # Modal detail divergence per emiten
│       └── command_palette.html    # Omnibar Quick Search (Ctrl + K)
│
├── static/                         # Asset Frontend (CSS & Vanilla JS Modular)
│   ├── css/
│   │   ├── base.css                # CSS Reset & Font Stack
│   │   ├── layout.css              # Tata letak app, sidebar, stats grid, admin user card
│   │   ├── table.css               # Styling tabel data responsif
│   │   ├── modals.css              # Styling dialog modal
│   │   ├── login.css               # Styling halaman login (Enterprise Clear & Green)
│   │   ├── command-palette.css     # Styling omnibar Ctrl+K
│   │   └── components/
│   │       └── stock_modal.css     # Styling Bento Grid modal saham, tab, badge, & button 28px
│   └── js/
│       ├── main.js                 # Initializer & router frontend
│       ├── login.js                # Form controller login AJAX & validasi
│       ├── core/
│       │   ├── scanner.js          # Polling status scan & trigger scanner
│       │   ├── stock_detail_modal.js # Controller tab modal detail & inline bandar checker
│       │   ├── utils.js            # Format rupiah, angka lot, format tanggal
│       │   └── export.js           # Export tabel ke CSV / Excel
│       ├── screeners/
│       │   ├── sepa.js             # Logic filtering & rendering tabel SEPA
│       │   ├── prebreakout.js      # Logic filtering & rendering tabel Pre-Breakout
│       │   └── rsi.js              # Logic filtering & rendering tabel RSI Divergence
│       └── components/
│           └── command-palette.js  # Controller shortcut Ctrl+K
│
├── data/                           # Data Storage & Cache Lokal
│   ├── idx_tickers.csv             # Universe 205 saham IDX aktif pilihan
│   ├── cache/
│   │   ├── scan_result.json        # Cache hasil scan SEPA terkini
│   │   ├── pre_breakout_result.json# Cache hasil scan Pre-Breakout terkini
│   │   ├── rsi_div_result.json     # Cache hasil scan RSI Divergence terkini
│   │   └── idx_api_cache.db        # SQLite database cache Broker Summary, Accumulation, Financials
│   └── cron_scan.log               # Log riwayat auto-scan cron
│
├── deploy/                         # Paket Konfigurasi Deployment VPS
│   ├── setup.sh                    # Skrip otomatis 1-klik instalasi di VPS Ubuntu
│   ├── tirexxz.service             # Systemd daemon file untuk Gunicorn
│   ├── nginx.conf                  # Nginx reverse proxy + static cache + SSL ready
│   ├── run_scan.py                 # Standalone CLI scan runner untuk Cron
│   ├── crontab.txt                 # Konfigurasi cron schedule jam 18:00 WIB
│   └── DEPLOYMENT_GUIDE.md         # Panduan instalasi step-by-step lengkap
│
└── ProjectOverview/                # Dokumentasi Spesifikasi & Panduan Teknis
    ├── PROJECT_OVERVIEW.md         # (File ini) Panduan induk status proyek untuk next agent
    ├── APISpecs.md                 # Dokumentasi spesifikasi API IDX Edge PRO
    ├── Indicator Templatate Sepa Trend # Pine Script acuan indikator SEPA TradingView
    ├── RSI Divergence              # Pine Script acuan RSI Divergence
    └── Screnner_SepaTrend          # Catatan formula dasar SEPA
```

---

## 4. Kredensial & Konfigurasi Default

| Komponen | Variabel | Nilai Default | Keterangan |
| :--- | :--- | :--- | :--- |
| **Admin Login** | `ADMIN_USERNAME` | `admin` | Diset di file [`.env`](file:///d:/Learning/SepaTrend/.env) |
| **Admin Password** | `ADMIN_PASSWORD` | `admin123` | Diset di file [`.env`](file:///d:/Learning/SepaTrend/.env) |
| **Flask Session** | `SECRET_KEY` | `tirexxz_super_secret_key_...` | Diset di file [`.env`](file:///d:/Learning/SepaTrend/.env) |
| **API Provider** | Base URL | `https://stock.arjum.com` | IDX Edge PRO |
| **API Key** | `X-API-Key` | `sk_live_pHzfNvhf-prFU2zXdclByx0tBdS8UyYOTKid3LY_lms` | Limit: 1.000 req/hari |

---

## 5. Catatan Penting & Known Gotchas (Must-Read untuk Next Agent!)

1. **Proteksi Nilai `NaN` pada Yahoo Finance**:
   * *Gotcha*: Pada akhir pekan (Sabtu/Minggu atau setelah market tutup), Yahoo Finance untuk ticker `.JK` kerap mengembalikan baris terakhir dengan nilai `Close: NaN`.
   * *Rule*: Selalu gunakan `.dropna(subset=['Close'])` pada DataFrame sebelum menghitung indikator MA, price, atau RS percentile. Seluruh evaluator (`calculator.py`, `pre_breakout.py`, `rsi_divergence.py`, dan `run_scan.py`) sudah menerapkan ini.

2. **Daftar Seller pada Broker Summary**:
   * *Gotcha*: Endpoint `/api/broker-summary/{ticker}` secara default hanya membatasi 20 broker net buyer teratas (`nval > 0`).
   * *Rule*: Selalu sertakan parameter `all_data=true` agar seluruh 41+ broker ditarik lengkap sehingga daftar Top 5 Net Sellers tidak kosong.

3. **Manajemen Kuota 1.000 Req/Hari**:
   * *Rule*: Jangan pernah melakukan loop batch ke endpoint IDX Edge PRO di dalam background scanner. Biarkan background scanner fokus menggunakan data gratisan Yahoo Finance untuk menyaring 205 saham menjadi ~30 saham potensial. Data IDX Edge PRO hanya dipanggil secara **On-Demand** ketika user mengklik tombol *"Cek Bandar"* atau membuka Modal Detail.

4. **Dynamic `.env` Loading**:
   * Modul `screener/auth.py` telah dikonfigurasi untuk membaca file `.env` secara real-time saat login dilakukan. Mengubah kredensial di `.env` tidak memerlukan restart server Flask.

---

## 6. Checklist Langkah Selanjutnya (Next Steps Roadmap)

Jika Anda adalah agen yang melanjutkan pengembangan proyek ini, berikut adalah daftar prioritas berikutnya sesuai arahan user:
- [x] **Fase 1**: Perbaikan data scan hilang (NaN dropna) & pemulihan data sellers/tren akumulasi SIMP.
- [x] **Fase 2**: Rebranding menjadi `Tirexxz Screnner` & pembersihan badge IDX.
- [x] **Fase 3**: Sistem Login & Session Management Admin dengan proteksi full-private screener.
- [x] **Fase 4**: Paket Konfigurasi Deployment VPS (Gunicorn, Nginx, Systemd, Cron Jam 18:00 WIB).
- [ ] **Fase 5 (Next)**: Eksekusi deploy ke server VPS pengguna ketika VPS sudah aktif dan IP/akses SSH diberikan.
- [ ] **Fase 6 (Opsional Masa Depan)**: Notifikasi otomatis sinyal breakout ke Telegram Bot / Discord Webhook pada saat Cron Scan selesai jam 18:00 WIB.
