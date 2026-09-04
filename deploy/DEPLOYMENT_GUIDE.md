# 🚀 Panduan Lengkap Deploy Tirexxz Screnner ke VPS Ubuntu

Panduan langkah demi langkah untuk mendeploy aplikasi **Tirexxz Screnner** ke server VPS (Ubuntu 22.04 atau 24.04 LTS) hingga berjalan live 24/7 dengan HTTPS SSL dan Auto-Scan harian otomatis.

---

## 📋 Ringkasan Arsitektur Produksi
* **Operating System**: Ubuntu 22.04 / 24.04 LTS (Rekomendasi RAM: 1 GB atau 2 GB)
* **Web Server / Reverse Proxy**: Nginx (dengan Gzip, HTTP/2, dan Static File Caching)
* **WSGI Application Server**: Gunicorn (3 workers, binding ke `127.0.0.1:5000`)
* **Process Manager / Daemon**: Linux Systemd (`tirexxz.service`)
* **Security & SSL**: HTTPS gratis via Let's Encrypt (Certbot auto-renewal)
* **Automation**: Cron Job (Auto-scan seluruh saham IDX setiap **Senin–Jumat jam 18:00 WIB**)

---

## Langkah 1: Akses SSH ke VPS Anda

Buka Terminal (atau PowerShell di Windows / PuTTY), lalu login ke server VPS Anda:

```bash
ssh root@IP_VPS_ANDA
```
*(Ganti `IP_VPS_ANDA` dengan alamat IP publik VPS Anda, misalnya `ssh root@103.187.99.12`)*

---

## Langkah 2: Upload / Pindahkan Kode Project ke VPS

Pindahkan seluruh folder project `SepaTrend` ke direktori standar web di VPS: `/var/www/tirexxz-screener`.

### Opsi A (Menggunakan Git / GitHub - Rekomendasi):
```bash
# Buat folder web dan clone repository Anda
mkdir -p /var/www
cd /var/www
git clone https://github.com/username-anda/SepaTrend.git tirexxz-screener
cd /var/www/tirexxz-screener
```

### Opsi B (Upload Langsung dari Komputer Lokal via SCP/Rsync):
Jalankan perintah ini dari terminal komputer lokal Anda (bukan di VPS):
```bash
scp -r d:/Learning/SepaTrend root@IP_VPS_ANDA:/var/www/tirexxz-screener
```

---

## Langkah 3: Jalankan Skrip Instalasi 1-Klik (`setup.sh`)

Masuk ke folder project di VPS dan jalankan skrip instalasi otomatis:

```bash
cd /var/www/tirexxz-screener
sudo bash deploy/setup.sh
```

**Apa yang dilakukan oleh skrip ini secara otomatis?**
1. Menginstall `python3-venv`, `python3-pip`, `nginx`, `git`, dan `certbot`.
2. Membuat virtual environment Python di `/var/www/tirexxz-screener/venv`.
3. Menginstall seluruh dependensi (`requirements.txt` termasuk `gunicorn`).
4. Menyiapkan file `.env` dengan `SECRET_KEY` unik yang aman.
5. Memasang dan mengaktifkan service background `tirexxz.service` di Systemd.
6. Memasang konfigurasi reverse proxy Nginx dan merestart web server.

---

## Langkah 4: Sesuaikan Kredensial Admin di File `.env`

Buka file konfigurasi `.env` di VPS:

```bash
nano /var/www/tirexxz-screener/.env
```

Ubah baris berikut sesuai keinginan Anda:
```ini
# Ganti dengan username dan password yang Anda inginkan
ADMIN_USERNAME=admin
ADMIN_PASSWORD=password_rahasia_anda_disini

# Pengaturan durasi sesi login
SESSION_LIFETIME_DAYS=7
REMEMBER_ME_DAYS=30
```
*Tekan `Ctrl + O` lalu `Enter` untuk menyimpan, kemudian `Ctrl + X` untuk keluar.*

---

## Langkah 5: Hubungkan Domain & Pasang HTTPS SSL Gratis

### 1. Arahkan DNS Domain ke IP VPS
Buka panel DNS domain Anda (Cloudflare, Niagahoster, Domainesia, dsb.), lalu buat **A Record**:
* **Name**: `@` atau `screener` (misal: `screener.namadomain.com`)
* **Target / IP**: Masukkan `IP_VPS_ANDA`
* **Proxy status**: DNS Only (jika menggunakan Cloudflare)

### 2. Pasang Nama Domain di Konfigurasi Nginx
Edit file Nginx di VPS:
```bash
sudo nano /etc/nginx/sites-available/tirexxz
```
Ubah baris `server_name` dengan nama domain Anda:
```nginx
server_name screener.namadomain.com;
```
Simpan (`Ctrl + O`, `Enter`, `Ctrl + X`), lalu reload Nginx:
```bash
sudo nginx -t
sudo systemctl reload nginx
```

### 3. Generate Sertifikat SSL HTTPS Gratis (Certbot)
Jalankan perintah ini:
```bash
sudo certbot --nginx -d screener.namadomain.com
```
* Masukkan email Anda saat diminta.
* Setujui Terms of Service (`Y`).
* Certbot akan secara otomatis memverifikasi domain, memasang sertifikat SSL, dan mengonfigurasi redirect otomatis dari HTTP ke HTTPS!

---

## Langkah 6: Pasang Otomasi Cron Auto-Scan (Senin–Jumat Jam 18:00 WIB)

Untuk memastikan data screener diperbarui secara otomatis setiap hari setelah jam bursa tutup dan settle:

Buka crontab editor:
```bash
crontab -e
```
*(Jika baru pertama kali, pilih editor nomor `1` yaitu nano).*

Tambahkan baris berikut di bagian paling bawah:
```cron
# Auto-Scan Tirexxz Screnner setiap Senin - Jumat jam 18:00 WIB
CRON_TZ=Asia/Jakarta
0 18 * * 1-5 /var/www/tirexxz-screener/venv/bin/python /var/www/tirexxz-screener/deploy/run_scan.py >> /var/log/tirexxz_cron.log 2>&1
```

*Tekan `Ctrl + O`, `Enter`, lalu `Ctrl + X` untuk menyimpan.*

---

## 🛠️ Perintah Operasional & Monitoring Penting

Gunakan perintah-perintah berikut kapan saja untuk mengelola server:

| Aksi | Perintah Linux |
| :--- | :--- |
| **Cek Status Aplikasi** | `sudo systemctl status tirexxz` |
| **Restart Aplikasi** | `sudo systemctl restart tirexxz` |
| **Lihat Log Aplikasi Live** | `sudo journalctl -u tirexxz -f` |
| **Lihat Log Error Gunicorn** | `tail -f /var/log/tirexxz_error.log` |
| **Lihat Log Auto-Scan Cron** | `tail -f /var/log/tirexxz_cron.log` |
| **Restart Nginx** | `sudo systemctl restart nginx` |
| **Test Manual Jalankan Scan** | `/var/www/tirexxz-screener/venv/bin/python /var/www/tirexxz-screener/deploy/run_scan.py` |

---

## 🎉 Selamat!
Aplikasi **Tirexxz Screnner** Anda kini telah live di server VPS, terlindungi login admin, terenkripsi SSL HTTPS, dan otomatis terupdate setiap hari bursa!
