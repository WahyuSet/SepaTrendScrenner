# 📈 Tirexxz Screnner — Enterprise Stock Screening Platform

> **Modern Indonesian Stock Exchange (IDX) Screener powered by Mark Minervini SEPA (Stage 2 Uptrend), Pre-Breakout Setups (VCP), RSI Bullish Divergence, and On-Demand Bandarmologi & Financial Analysis.**

---

## 🌟 Fitur Utama

### 1. 📊 Tiga Mesin Screener Saham IDX
- **SEPA Trend Screener**: Evaluasi 8 kriteria Mark Minervini Stage 2 Uptrend (MA50, MA150, MA200 alignment, MA200 slope lookback, 52-week High/Low distance, dan IBD Relative Strength Rating vs IHSG `^JKSE`).
- **Pre-Breakout Setup**: Deteksi konsolidasi harga volatilitas menyusut (Volatility Contraction Pattern / VCP) di bawah resistance terdekat (<5%) dengan Relative Volume (RVOL) dan turnover minimum Rp500 Juta.
- **RSI Bullish Divergence**: Deteksi otomatis pola pembalikan arah *Regular Bullish* dan kelanjutan tren *Hidden Bullish*.

### 2. 🔍 Integrasi Bandarmologi & Finansial On-Demand (IDX Edge PRO)
- **Broker Summary**: Top 5 Net Buyers & Net Sellers, volume, turnover, dan rasio konsentrasi akumulasi/distribusi bandar.
- **Tren Akumulasi 7 Hari**: Grafik pergerakan net flow akumulasi bandar selama 7 hari bursa terakhir.
- **Laporan Keuangan Kuartalan**: Pertumbuhan EPS dan Laba Bersih secara YoY (Year-over-Year).
- **AI Verdict & Trading Plan**: Sinyal rekomendasi, Daily Pivots (R2, R1, P, S1, S2), dan panduan posisi taktis.
- **Smart SQLite Caching**: Proteksi kuota harian dengan sistem cache lokal SQLite per hari bursa.

### 3. 🛡️ Keamanan & Manajemen Sesi Administrator
- **Full Private Mode**: Seluruh halaman dashboard dan API dilindungi login admin.
- **Kredensial Dinamis `.env`**: Username dan password dikonfigurasi melalui file `.env`.
- **Sesi Enkripsi HMAC SHA-256**: Durasi sesi 7 hari (atau 30 hari jika opsi "Ingat Saya" dicentang).
- **Brute-Force Protection**: Rate limiter otomatis (maksimal 5x kesalahan per 15 menit).

### 4. ⚡ Siap Deploy VPS 24/7
- Konfigurasi lengkap Gunicorn WSGI + Nginx Reverse Proxy + Linux Systemd Daemon + Cron Auto-Scan jam 18:00 WIB.

---

## 🚀 Panduan Menjalankan di Komputer Lokal

### 1. Clone Repository & Setup Virtualenv
```bash
git clone https://github.com/WahyuSet/SepaTrendScrenner.git
cd SepaTrendScrenner

# Buat virtual environment
python -m venv venv

# Aktifkan virtualenv:
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install dependensi
pip install -r requirements.txt
```

### 2. Konfigurasi Lingkungan (`.env`)
Salin template `.env.example` menjadi `.env`:
```bash
cp .env.example .env
```
Buka file `.env` dan atur username serta password admin yang Anda inginkan:
```ini
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123
SECRET_KEY=masukkan_secret_key_acak_disini
```

### 3. Jalankan Aplikasi
```bash
python app.py
```
Buka browser di `http://127.0.0.1:5000` dan login menggunakan kredensial yang telah Anda tentukan.

---

## 🌐 Panduan Deployment ke VPS

Paket instalasi otomatis telah tersedia di folder `deploy/`. Silakan baca panduan lengkap pada:
👉 [deploy/DEPLOYMENT_GUIDE.md](deploy/DEPLOYMENT_GUIDE.md)

Langkah cepat instalasi 1-klik di VPS Ubuntu 22.04 / 24.04 LTS:
```bash
cd /var/www/tirexxz-screener
sudo bash deploy/setup.sh
sudo certbot --nginx -d screener.namadomain.com
```

---

## 📁 Struktur Proyek

```
├── app.py                      # Flask App Core & Protected API Routes
├── requirements.txt            # Dependensi Python
├── .env.example                # Template konfigurasi environment
├── screener/                   # Algoritma SEPA, RSI, Pre-Breakout & Auth
├── templates/                  # HTML Templates (Dashboard & Enterprise Login)
├── static/                     # CSS Tokens & Vanilla JS Modules
├── data/                       # Universe IDX Tickers & Cache Files
├── deploy/                     # Paket Deployment VPS (Systemd, Nginx, Cron, Setup)
└── ProjectOverview/            # Dokumentasi Spesifikasi & Panduan Teknis
```

---

## 📄 Lisensi
Hak cipta dilindungi. Dikembangkan untuk penggunaan pribadi dan institusi analisa pasar modal Indonesia.
