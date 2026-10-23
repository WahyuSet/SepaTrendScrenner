# Rencana Implementasi: Refactor UI Tirexxz Screnner

**Tanggal**: 2026-10-22
**Arah desain**: [Design.md](Design.md) v2.0 (keputusan D-1 sampai D-8, usulan P-1 sampai P-5)
**Filter**: antislop (core + antislop-ui), mode DURING
**Cakupan**: `templates/`, `static/css/`, `static/js/`. Backend (`app.py`, `screener/`) tidak disentuh.

---

## 1. Kondisi Awal (audit 2026-10-22)

| Masalah | Angka | Rule |
|---|---|---|
| `--text-muted: #94a3b8`, kontras 2.56:1 | 63 pemakaian | R-25 |
| Warna hex berbeda di CSS | 97 nilai, sekitar 735 hex mentah di luar `base.css` | R-29 |
| Emoji di template dan JS | 328 di 32 file | R-04 |
| Em dash di teks UI | sekitar 92 | R-02 |
| Animasi `infinite` di luar loading | radarPing, radarPingAmber, heartPulse, pulseGlow, pulseScopeDot | R-19 |
| `translateY(-...)`, sebagian besar efek hover | 24 tempat di 11 file | R-19 (D-3) |
| `backdrop-filter` | 8 deklarasi di 4 file | R-10 |
| `outline: none` | 7 tempat | R-32 |
| `<div>/<span>/<tr>` dengan `onclick` | 17 di template, 17 di JS | R-32 |
| Modal yang bisa ditutup Escape | 2 dari 8 modal (+ drawer) | R-32 |
| `role="dialog"` | 1 dari 8 modal | R-32 |
| `onclick=` inline di template | 187 | Kualitas |
| `style="..."` di HTML hasil JS | 63 | Kualitas |
| `!important` | 38 (24 di `watchlist.css`) | Kualitas |
| `stock_modal.css` dimuat dua kali; `style.css` pakai rantai `@import` | | Kinerja |
| Mode gelap | tidak ada | D-2 |

Yang sudah baik dan dipertahankan: palet lime + status sudah konsisten secara konsep, `tabular-nums`, ticker mono, focus ring global di `base.css`, semua data nyata.

---

## 2. Aturan Kerja (berlaku di semua fase)

1. **Branch**: kerjakan di `refactor/ui-antislop`. Satu commit per fase atau per kelompok file dalam fase. Jangan commit file `data/cache/*.json`.
2. **Jangan putus hook JS**: sebelum mengganti nama class atau ID, cari dulu di `static/js/`. Kalau dipakai JS, nama dipertahankan sampai Fase 9. Struktur DOM yang dibangun JS (baris tabel, badge) diubah di file JS yang sama dalam fase yang sama.
3. **Hanya token**: setiap file CSS yang disentuh keluar dalam keadaan tanpa hex mentah. Warna baru selalu masuk `tokens.css` dulu.
4. **Tidak ada patch script** (R-33): semua perubahan ditulis langsung di file sumber, bukan lewat script `str.replace`.
5. **Copy ikut dibersihkan**: em dash dan emoji di file yang sedang disentuh langsung dibereskan di fase itu. Fase 8 hanya menyapu sisanya.
6. **Verifikasi per fase** memakai server preview `sepatrend-preview` (`scratch/dev_preview.py`, port 5055, sesi admin otomatis, khusus lokal). Login asli diuji di Fase 2 pada server `sepatrend` (port 5000) oleh pemilik.
7. **Matriks uji per fase**: lebar 360, 768, 1024, 1440 × mode terang dan gelap, plus keyboard saja (Tab, Shift+Tab, Enter, Escape) untuk elemen yang disentuh. Console browser harus bersih dari error.
8. **Bukti**: setiap fase ditutup dengan daftar klik per elemen (contoh: "Nav RSI Divergence → view RSI tampil, `aria-current` pindah, tanpa error console") dan screenshot sebelum/sesudah.

---

## 3. Fase

Urutan disusun supaya setiap fase bisa dirilis sendiri dan tampilan tidak pernah rusak di tengah jalan. Perkiraan ukuran: S (< 2 jam), M (setengah hari), L (1 hari atau lebih).

### Fase 0: Persiapan (S)

**Tujuan**: titik awal yang bisa dibandingkan.

Langkah:
1. Buat branch `refactor/ui-antislop` dari `main`.
2. Jalankan `sepatrend-preview`, ambil screenshot baseline setiap view (7 view + 8 overlay + login) di 1440px dan 375px. Simpan di `scratch/ui-baseline/` (tidak di-commit).
3. Catat daftar semua kontrol interaktif per view sebagai checklist klik (dipakai ulang di setiap fase).

Selesai jika: baseline screenshot dan checklist klik ada.

---

### Fase 1: Fondasi Token dan Mekanisme Tema (M)

**Tujuan**: semua warna, spacing, radius, dan elevasi berasal dari satu file token, dengan dua mode. Tampilan mode terang nyaris sama dengan sekarang, kecuali kontras teks muted yang diperbaiki.

File: `static/css/base.css`, file baru `static/css/tokens.css`, `static/css/style.css`, `templates/index.html`, `templates/login.html`, lalu semua file CSS untuk penggantian hex.

Langkah:
1. Buat `static/css/tokens.css` berisi token mode terang dan gelap persis seperti Design.md §3.2, §3.3, §3.5, §4.2, §5.1, §5.2. Tambahkan alias `--status-div-reg-*` dan `--status-div-hid-*`.
2. Pindahkan blok `:root` dari `base.css` ke `tokens.css`. `base.css` tinggal reset, body, focus, scrollbar, utilitas, toast.
3. Tambahkan aturan `prefers-reduced-motion` global (Design.md §8) di `base.css`.
4. Ganti rantai `@import` di `style.css` dengan daftar `<link>` berurutan di `index.html`: `tokens.css`, `base.css`, `layout.css`, `table.css`, `modals.css`, `command-palette.css`, komponen, screener. Hapus `<link>` ganda `stock_modal.css`. Hapus `style.css` kalau sudah kosong.
5. Kurangi weight Google Fonts: Plus Jakarta Sans 400;500;600;700, JetBrains Mono 500;600.
6. Tambahkan script tema inline di `<head>` `index.html` dan `login.html` (Design.md §3.6), dengan `try/catch` di sekitar `localStorage`.
7. Ganti hex mentah dengan token, file per file, dari yang terbesar: `market_regime.css` (157), `watchlist.css` (153), `stock_modal.css` (124), `backtest.css` (89), `quality_setup.css` (56), `layout.css` (53), `table.css` (34), `login.css` (33), `modals.css` (15), `rsi.css` (12), `command-palette.css` (8), `prebreakout.css` (3), `sepa.css` (1). Warna yang tidak punya padanan token dipetakan ke token terdekat sesuai perannya (§3.1), bukan dibuatkan token baru.
8. Hapus pemakaian `--shadow-card`, `--shadow-hover`, `--shadow-lime`, `--brand-lime-glow`. Kartu jadi datar (P-5).

Selesai jika:
- `grep -rniE "#[0-9a-f]{3,6}\b" static/css --include=*.css | grep -v tokens.css` kosong.
- Mengubah `data-theme` lewat devtools menghasilkan mode gelap yang terbaca di semua view (masih boleh ada detail yang belum rapi, dicatat untuk fase berikutnya).
- Tidak ada request CSS ganda di tab Network.
- Matriks uji mode terang tidak menunjukkan regresi dibanding baseline.

Risiko: pemetaan warna yang salah. Mitigasi: bandingkan screenshot terhadap baseline per file.

---

### Fase 2: Shell (sidebar, topbar, footer, login, toggle tema) (M)

File: `templates/components/sidebar.html`, `templates/components/footer.html`, `templates/index.html` (topbar), `templates/login.html`, `static/css/layout.css`, `static/css/login.css`, `static/js/main.js`, `static/js/login.js`, `static/favicon.svg` (tidak diubah, lihat catatan).

Langkah:
1. Nav: ganti emoji (📈📉🎯💎⭐🏦🧮🧪) dengan SVG sesuai pemetaan Design.md §6.11. Tambahkan `aria-current="page"` pada nav aktif di `switchScreener()`.
2. Hapus badge `CALC` dan `LAB`. Badge jumlah menampilkan `--` sebelum ada data, bukan em dash.
3. Search trigger dan tombol scan: ganti 🔍 dan ⚡ dengan SVG. Tombol scan memakai varian primary (§6.7), tanpa shadow lime dan tanpa geser saat hover.
4. Status pasar: hapus animasi `radarPing`/`radarPingAmber` dan gradient pill. Titik statis berwarna sesuai state.
5. Kartu user: hapus titik "Online" dan label "Online".
6. Tambahkan tombol toggle tema di sidebar bawah (§3.6), dengan `aria-pressed` dan simpan ke `localStorage`.
7. Topbar mobile: ganti emoji 🔍 dan ⚡ dengan SVG + `aria-label`. Brand di topbar diubah dari `<div onclick>` menjadi `<button>`.
8. Footer: hapus emoji ❤️ dan animasi `heartPulse`. Teks jadi "Tirexxz Screnner v2.0 · © 2026" atau versi lain yang disetujui pemilik saat review fase ini.
9. Login: terapkan token, hapus `pulseGlow`, hapus emoji dan em dash, pastikan field punya `<label>`, error login tampil dengan `role="alert"`.
10. Judul tab: hapus em dash (Design.md §11). Hapus favicon cadangan berbasis emoji di `<link rel="alternate icon">`.

Catatan logo: `static/favicon.svg` saat ini hanya membungkus emoji 🦖 di kotak gradient. Dibiarkan sampai pemilik menyediakan logo SVG (D-8). Tidak ada aset logo baru yang dibuat.

Selesai jika:
- Tidak ada emoji di `sidebar.html`, `footer.html`, topbar, `login.html`, kecuali logo 🦖.
- `grep -n "infinite" static/css/layout.css static/css/login.css` hanya menyisakan spinner loading.
- Toggle tema bekerja, pilihan bertahan setelah reload, tidak ada kedip putih saat memuat di mode gelap.
- Login asli diuji pemilik di server `sepatrend` (port 5000): berhasil, gagal, dan logout.
- Klik semua item nav, search, scan, refresh, logout, toggle tema di 1440px dan 375px, dua mode.

---

### Fase 3: View Screener dan Tabel (L)

File: `templates/views/view_sepa.html`, `view_rsi.html`, `view_prebreakout.html`, `view_quality_setup.html`, `templates/components/market_regime_banner.html`, `static/css/table.css`, `static/css/screeners/sepa.css`, `rsi.css`, `prebreakout.css`, `quality_setup.css`, `static/css/components/market_regime.css`, `static/js/screeners/sepa.js`, `rsi.js`, `prebreakout.js`, `quality_setup.js`, `static/js/core/utils.js`.

Langkah:
1. Buat komponen Summary Bar (Design.md §6.3) di `layout.css`. Ganti 4 stat card di 4 view screener. ID elemen angka (`stat-scanned`, `stat-confirmed`, dan seterusnya) dipertahankan supaya JS tetap mengisinya. Hapus kartu statis "IHSG Benchmark: Aktif".
2. View header: hapus em dash di judul, deskripsi satu baris.
3. Tabel (`table.css`): hapus `transform` di hover baris, `transition` hanya `background-color`. Ganti `outline: none` di `table.css` (2 tempat) dengan focus yang terlihat.
4. Baris yang bisa diklik: tambahkan `tabindex="0"` dan handler Enter di JS pembangun baris (sepa/rsi/prebreakout/quality).
5. Warna data sesuai Design.md §3.4: RS Rating, score bar, perubahan harga, badge kriteria C1-C8 (terisi vs outline + `aria-label`).
6. Fade-in baris: hanya saat hasil scan pertama tampil (D-4). Flag di JS, bukan di setiap render.
7. Pindahkan `style="..."` warna di HTML hasil JS (sepa 17, prebreakout 16, rsi 13, quality 11) ke class. `style` untuk lebar bar yang dinamis boleh tetap.
8. Market regime banner: hapus gradient, ikon 🏛️, dan glow. Badge regime pakai warna status. Tambahkan state memuat dan gagal (§6.2).
9. Verifikasi kolom tabel SEPA terhadap kode dan perbarui tabel di Design.md §6.5 kalau berbeda.

Selesai jika:
- Tidak ada `.stat-card` di 4 view screener.
- `grep -n "translateY\|translateX" static/css/table.css static/css/screeners/{sepa,rsi,prebreakout,quality_setup}.css static/css/components/market_regime.css` hanya menyisakan animasi masuk modal/toast.
- Tab sampai ke baris tabel, Enter membuka detail, focus terlihat di dua mode.
- Klik sort, filter, export, buka detail, link TradingView di setiap screener.

---

### Fase 4: Watchlist, LPM, Backtest (L)

File: `templates/views/view_watchlist.html`, `view_lpm.html`, `view_backtest.html`, `static/css/screeners/watchlist.css`, `backtest.css`, `static/css/components/lpm_panel.css`, `static/js/screeners/watchlist.js`, `backtest.js`, `static/js/core/lpm_panel.js`.

Langkah:
1. Watchlist: Summary Bar menggantikan stat card. Rapikan 24 `!important` di `watchlist.css` dengan memperbaiki urutan dan spesifisitas selector. Ganti `outline: none` (1 tempat).
2. Backtest: metrik memakai Summary Bar ukuran besar (§6.3). Hapus `pulseScopeDot` dan emoji (22 di template). Ganti `outline: none` (1 tempat).
3. LPM: chart membaca warna dari CSS variable (§3.5) saat dibuat, dan dirender ulang dengan warna baru saat event ganti tema. Hapus hex di JS. Label "eksperimental" tetap ada.
4. Bersihkan em dash dan emoji di tiga view dan JS-nya.

Selesai jika:
- Ganti tema saat view LPM terbuka langsung mengubah warna chart tanpa reload.
- Tambah, ubah, hapus entri watchlist dan jurnal bekerja. Jalankan satu backtest dan hasilnya tampil.
- `grep -c "!important" static/css/screeners/watchlist.css` menunjukkan 0, atau setiap sisa punya komentar alasan.

---

### Fase 5: Sistem Modal dan Overlay (M)

File: `templates/modals/*.html` (8 file + `command_palette.html`), `static/css/modals.css`, `command-palette.css`, `components/stock_modal.css`, `static/js/core/utils.js` (helper modal), `static/js/core/stock_detail_modal.js`, `static/js/components/command-palette.js`, `position_calculator.js`, dan fungsi tutup modal di `sepa.js`, `rsi.js`, `prebreakout.js`, `quality_setup.js`, `watchlist.js`.

Langkah:
1. Buat helper modal bersama di `utils.js`: `openModal(id, triggerEl)` dan `closeModal(id)`. Isinya: atur `aria-hidden`, pindahkan fokus, perangkap Tab, Escape, klik backdrop, kembalikan fokus ke pemicu.
2. Semua modal: `role="dialog"`, `aria-modal="true"`, `aria-labelledby`. Fungsi tutup per screener (`closeModal`, `closeRsiModal`, `closePreBreakoutModal`, `closeQualityModal`, dan seterusnya) dialihkan ke helper, nama fungsi lama dipertahankan sebagai pembungkus supaya `onclick` di template tetap jalan.
3. `backdrop-filter` hanya di backdrop modal dan backdrop command palette. Hapus dari `layout.css` dan `stock_modal.css` di tempat lain.
4. Position Sizing: ubah "bento grid" menjadi daftar hasil (label + nilai), hapus emoji 🛑 dan sejenisnya (§6.8).
5. Command palette: emoji (21 di JS) diganti SVG atau dihapus. Ganti `outline: none` (2 tempat) dengan focus yang terlihat. Pastikan panah atas/bawah dan Enter berfungsi.
6. Modal tampil layar penuh di ≤480px.
7. Toast: `role="status"` / `role="alert"`, tombol tutup.

Selesai jika:
- Setiap modal (8) dan command palette: buka dengan klik dan dengan keyboard, Tab tidak keluar dari modal, Escape menutup, fokus kembali ke pemicu, klik backdrop menutup.
- `grep -rn "backdrop-filter" static/css` hanya 2 hasil.

---

### Fase 6: State Data dan Sapuan Aksesibilitas (M)

File: semua view, `static/js/core/scanner.js`, JS screener, `static/css/table.css`.

Langkah:
1. Untuk setiap view, terapkan empat state di Design.md §7 (loading, kosong belum scan, kosong hasil filter, error) dengan teks yang menyebut penyebab dan aksi. Hapus ikon emoji di `empty-state-icon`.
2. Simulasikan setiap state: cache kosong, filter yang tidak cocok, server mengembalikan error (matikan endpoint sementara di devtools dengan request blocking).
3. Sisa `<div>/<span>/<td>` dengan `onclick` (17 di template, 17 di JS) diganti `<button>`, atau diberi `role`, `tabindex`, dan handler keyboard kalau harus tetap berupa baris tabel.
4. Progres scan dan toast memakai `aria-live`.
5. Cek kontras semua kombinasi teks dan background yang muncul di dua mode, termasuk badge di atas background tint.

Selesai jika:
- Setiap view menampilkan state yang benar untuk keempat kondisi, dua mode.
- Seluruh aplikasi bisa dipakai hanya dengan keyboard: pindah view, scan, buka detail, tutup modal, ganti tema, logout.
- `grep -rn "outline: *\(none\|0\)" static/css` tidak menyisakan tempat tanpa pengganti focus.

---

### Fase 7: Konsolidasi Responsif (M)

File: `layout.css`, `table.css`, `market_regime.css`, `backtest.css`, `lpm_panel.css`, `quality_setup.css`, `modals.css`.

Langkah:
1. Satukan breakpoint ke 1024 / 768 / 480 (Design.md §9). Ganti breakpoint lain (1280, 992, 900, 640, 600, 400) dengan breakpoint standar terdekat.
2. Pastikan drawer di ≤1024px: buka, tutup dengan backdrop dan Escape, fokus pindah ke drawer.
3. Tabel: scroll horizontal di dalam kartu, kolom ticker sticky kiri.
4. Target sentuh 44px lewat `@media (pointer: coarse)`.
5. Uji 360px untuk overflow: `document.documentElement.scrollWidth <= innerWidth` di setiap view dan setiap modal.

Selesai jika: tidak ada scroll horizontal halaman di 360, 768, 1024, 1440 untuk semua view dan overlay, dua mode.

---

### Fase 8: Sapuan Copy dan Delivery Gate (S)

Langkah:
1. Cari sisa em dash dan emoji di `templates/` dan `static/js/`, bereskan (kecuali logo 🦖).
2. Cek label tombol sesuai Design.md §11.
3. Jalankan Delivery Gate antislop lengkap (Hard Gate, Purpose-Gate, Liveliness, Craftsmanship) dan tulis laporannya di `anti-slop/delivery-gate-2026-MM-DD.md`, setiap PASS dengan bukti.
4. Perbarui Design.md kalau ada keputusan yang berubah selama implementasi.

Selesai jika:
- `grep -rn "—" templates static/js` kosong.
- Hitungan emoji di `templates/` dan `static/js/` hanya logo.
- Laporan Delivery Gate tanpa FAIL.

---

### Fase 9 (opsional): Rapikan JS (L)

Dikerjakan hanya setelah Fase 0-8 selesai dan stabil.

Langkah:
1. Ganti 187 `onclick` inline dengan atribut `data-action` + satu event listener terdelegasi di `main.js`.
2. `switchScreener()` jadi berbasis tabel konfigurasi, bukan rantai `if/else` per view.
3. Ganti nama class yang tidak lagi sesuai isinya (contoh: `calc-bento-grid`, `bento-stat-card`).

Selesai jika: checklist klik Fase 0 lolos seluruhnya tanpa error console.

---

## 4. Ringkasan Urutan

| Fase | Isi | Ukuran | Bergantung pada |
|---|---|---|---|
| 0 | Persiapan dan baseline | S | |
| 1 | Token dan mekanisme tema | M | 0 |
| 2 | Shell, login, toggle tema | M | 1 |
| 3 | View screener dan tabel | L | 1 |
| 4 | Watchlist, LPM, Backtest | L | 1 |
| 5 | Modal dan overlay | M | 1 |
| 6 | State data dan aksesibilitas | M | 3, 4, 5 |
| 7 | Konsolidasi responsif | M | 2-6 |
| 8 | Sapuan copy dan Delivery Gate | S | 7 |
| 9 | Rapikan JS (opsional) | L | 8 |

Fase 3, 4, dan 5 menyentuh file yang berbeda dan bisa dikerjakan paralel setelah Fase 1. Satu-satunya file bersama adalah `utils.js` (Fase 3 dan 5), jadi helper modal Fase 5 ditaruh di bagian file terpisah, atau Fase 3 dan 5 dikerjakan berurutan.

## 5. Di Luar Cakupan

- Perubahan backend, endpoint API, atau logika screener.
- Logo SVG baru (menunggu pemilik, D-8).
- Migrasi ke framework frontend atau build tool. Stack tetap Flask + Jinja + vanilla JS + CSS.
