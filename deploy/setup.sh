#!/usr/bin/env bash
# ==============================================================================
# TIREXXZ SCRENNER - AUTOMATED 1-CLICK VPS SETUP SCRIPT (UBUNTU / DEBIAN)
# Jalankan skrip ini dengan hak akses sudo:
# sudo bash deploy/setup.sh
# ==============================================================================

set -e

APP_DIR="/var/www/tirexxz-screener"
APP_USER="www-data"

echo "==========================================================="
echo "🚀 MEMULAI SETUP OTOMATIS TIREXXZ SCRENNER DI VPS..."
echo "==========================================================="

# 1. Update paket sistem
echo "📦 [1/7] Memperbarui paket sistem dan menginstall dependensi dasar..."
apt update && apt upgrade -y
apt install -y python3 python3-pip python3-venv nginx git curl certbot python3-certbot-nginx

# 2. Buat folder dan set permission
echo "📂 [2/7] Menyiapkan direktori aplikasi di ${APP_DIR}..."
mkdir -p "${APP_DIR}/data/cache"
mkdir -p "/var/log/nginx"

# 3. Setup Python Virtual Environment
echo "🐍 [3/7] Membuat Python Virtual Environment dan install requirements..."
if [ ! -d "${APP_DIR}/venv" ]; then
    python3 -m venv "${APP_DIR}/venv"
fi

"${APP_DIR}/venv/bin/pip" install --upgrade pip
"${APP_DIR}/venv/bin/pip" install -r "${APP_DIR}/requirements.txt"

# 4. Setup File .env jika belum ada
echo "⚙️ [4/7] Memeriksa file konfigurasi .env..."
if [ ! -f "${APP_DIR}/.env" ]; then
    cp "${APP_DIR}/.env.example" "${APP_DIR}/.env"
    # Generate random secret key
    RANDOM_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    sed -i "s/change_this_to_a_secure_random_string_on_vps/${RANDOM_KEY}/g" "${APP_DIR}/.env"
    echo "   -> File .env berhasil dibuat dari template dengan SECRET_KEY unik acak."
    echo "   -> Silakan edit .env nanti untuk mengubah ADMIN_USERNAME dan ADMIN_PASSWORD Anda."
fi

# Set kepemilikan folder ke www-data
chown -R ${APP_USER}:${APP_USER} "${APP_DIR}"
chmod -R 775 "${APP_DIR}/data"

# 5. Pasang Systemd Service (Gunicorn)
echo "⚡ [5/7] Mengonfigurasi Systemd Service (tirexxz.service)..."
cp "${APP_DIR}/deploy/tirexxz.service" /etc/systemd/system/tirexxz.service
systemctl daemon-reload
systemctl enable tirexxz
systemctl restart tirexxz

# 6. Pasang Nginx Reverse Proxy
echo "🌐 [6/7] Mengonfigurasi Nginx Reverse Proxy..."
cp "${APP_DIR}/deploy/nginx.conf" /etc/nginx/sites-available/tirexxz
ln -sf /etc/nginx/sites-available/tirexxz /etc/nginx/sites-enabled/tirexxz

# Hapus default nginx site jika masih aktif
if [ -f /etc/nginx/sites-enabled/default ]; then
    rm /etc/nginx/sites-enabled/default
fi

nginx -t
systemctl reload nginx

# 7. Selesai
echo "==========================================================="
echo "✅ DEPLOYMENT VPS SELESAI DENGAN SUKSES!"
echo "==========================================================="
echo "1. Cek status service:      sudo systemctl status tirexxz"
echo "2. Cek status Nginx:        sudo systemctl status nginx"
echo "3. Pasang Domain & SSL:     sudo certbot --nginx -d namadomain.com"
echo "4. Pasang Auto-Scan Cron:   crontab -e  (lihat deploy/crontab.txt)"
echo "==========================================================="
