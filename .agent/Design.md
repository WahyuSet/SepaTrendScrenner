# Design System: Tirexxz Screnner
**Frontend Design Document**
**Versi**: 2.0
**Tanggal**: 2026-10-22
**Menggantikan**: v1.0 (2026-09-01)
**Filter**: antislop (core + antislop-ui), mode DURING
**Rencana eksekusi**: [UI_REFACTOR_PLAN.md](UI_REFACTOR_PLAN.md)

---

## 0. Catatan Revisi v2

### 0.1 Keputusan pemilik (2026-10-22)

| # | Topik | Keputusan | Menggantikan v1 |
|---|---|---|---|
| D-1 | Mobile | Responsif penuh, phone sampai desktop | §12 "desktop-only, minimum 1024px" |
| D-2 | Tema | Terang sebagai default, plus toggle mode gelap. Dua mode wajib lolos kontras | Tema terang saja |
| D-3 | Hover | Tidak ada elemen yang bergeser saat hover. Feedback lewat warna background/border | `translateY` di card/button, `translateX` di baris tabel |
| D-4 | Row fade-in | Hanya saat hasil scan pertama kali tampil, mati saat `prefers-reduced-motion` | Fade-in setiap render tabel |
| D-5 | Stat cards | 4 stat card per screener diringkas jadi satu Summary Bar | §5.2 Stats Cards |
| D-6 | Placeholder | Tidak ada data palsu. Placeholder jujur (`--`, "Memuat...") boleh | Prinsip "No Placeholders" |
| D-7 | Nama | "Tirexxz Screnner" disengaja, tidak diubah | Nama "IDX SEPA Trend Screener" |
| D-8 | Logo | Emoji 🦖 dipakai sebagai logo **sementara**, sampai pemilik menyediakan logo SVG | Logo teks "◈ IDX SEPA" |

### 0.2 Usulan agent yang sudah diterapkan (ubah jika tidak setuju)

| # | Usulan | Alasan |
|---|---|---|
| P-1 | Dial ENERGY 1 / RHYTHM 2 / MOTION 1 | Alat kerja harian, tabel harus jadi pusat perhatian (§1.2) |
| P-2 | Lime khusus untuk aksi dan navigasi, tidak pernah untuk status data | Lime brand dan hijau "Confirmed" terlalu mirip, melanggar prinsip Zero Ambiguity (§3.1) |
| P-3 | `--text-muted` jadi `#5b6b80` | `#94a3b8` di kode cuma 2.56:1, `#64748b` di v1 gagal di atas hover `#f1f5f9` (4.34:1) |
| P-4 | Warna RS 70-89 diganti dari `hsl(77, 60%, 55%)` | Kontrasnya sekitar 1.8:1, tidak terbaca (§3.4) |
| P-5 | Kartu tanpa shadow, shadow hanya untuk overlay | Kalau semua elemen melayang, elevasi tidak berarti apa-apa (§5.3) |

---

## 1. Filosofi Desain

### 1.1 Produk dan pekerjaan utamanya

Tirexxz Screnner adalah workspace screener saham IDX untuk swing trader, dipakai oleh satu admin. Pekerjaan utama di setiap layar screener: **menemukan kandidat saham dari hasil scan, lalu memutuskan mana yang dibuka detailnya**. Tabel hasil adalah halaman utamanya. Banner, ringkasan, dan sidebar melayani tabel itu.

Prinsip "Enterprise Clear": bersih, padat informasi, data mudah dibaca dalam sesi panjang.

**Prinsip utama:**
- **Data First**: setiap elemen UI melayani informasi. Elemen yang tidak membawa informasi atau aksi dihapus.
- **Zero Ambiguity**: status saham (Confirmed, Watchlist, Fail) terbaca dalam hitungan detik, dari teks dan warna sekaligus, bukan dari warna saja.
- **Feedback tanpa gerak**: setiap elemen interaktif memberi feedback yang jelas (hover, focus, active, disabled) lewat warna dan border, bukan lewat geseran.
- **Data jujur**: tidak ada angka, nama, atau status palsu. Sebelum data ada, tampilkan placeholder jujur (`--`, "Memuat...", "Belum pernah scan").

### 1.2 Design Read dan dial

> Reading this as: workspace screener saham yang padat data untuk satu trader IDX, dalam gaya Enterprise Clear terang dengan mode gelap, dial ENERGY 1 / RHYTHM 2 / MOTION 1.

`Dial: ENERGY 1 / RHYTHM 2 / MOTION 1`

| Dial | Nilai | Artinya di produk ini |
|---|---|---|
| ENERGY | 1 (tenang) | Tidak ada gradient dekoratif, glow, atau emoji. Satu-satunya warna yang "bersuara" adalah lime di tombol aksi utama |
| RHYTHM | 2 (konsisten, dengan beberapa jeda) | Semua screener memakai struktur yang sama (header, summary, toolbar, tabel) supaya mudah dipindai. Jeda yang disengaja: market regime banner di atas, dan LPM/Backtest yang isinya chart dan metrik |
| MOTION | 1 (hanya state) | Gerak hanya untuk perubahan state: hover warna, buka/tutup modal, toast, loading. Tidak ada animasi yang berulang terus |

### 1.3 Motif identitas

Kode ticker dalam JetBrains Mono tebal, angka tabular yang rata kanan, dan lime yang hanya muncul di aksi. Tiga hal ini diulang di semua screener dan membuat tampilannya terasa milik produk ini.

---

## 2. Struktur Layout

### 2.1 Tipe layout: Sidebar + Main Content

```
┌─────────────────────────┬──────────────────────────────────────────┐
│ SIDEBAR (260px, sticky) │ MAIN CONTENT                             │
│                         │                                          │
│ 🦖 Tirexxz Screnner     │ Market Regime Banner (IHSG)              │
│ [Cari emiten... Ctrl K] │                                          │
│                         │ View Header (judul + deskripsi 1 baris)  │
│ SCREENERS               │ Summary Bar (angka nyata, 1 baris)       │
│  SEPA Trend         23  │ Toolbar (cari, filter, sort, export)     │
│  RSI Divergence     12  │ ┌──────────────────────────────────────┐ │
│  Pre-Breakout        8  │ │ Data Table                           │ │
│  Quality Setup       5  │ │ (fokus utama layar)                  │ │
│                         │ │                                      │ │
│ PORTOFOLIO & TOOLS      │ └──────────────────────────────────────┘ │
│  Watchlist & Journal 4  │                                          │
│  LPM & Smart Money      │ Footer                                   │
│  Position Sizing        │                                          │
│  Signal Backtest Lab    │                                          │
│                         │                                          │
│ [ Scan IDX Sekarang ]   │                                          │
│ progress scan           │                                          │
│                         │                                          │
│ ● IDX Open    [refresh] │                                          │
│ Update: 15:32 WIB       │                                          │
│ API Quota  412 / 1000   │                                          │
│ Administrator  [logout] │                                          │
│ [Mode gelap]            │                                          │
│ Tirexxz Screnner v2.0   │                                          │
└─────────────────────────┴──────────────────────────────────────────┘
```

Di layar ≤1024px sidebar menjadi drawer, dan topbar menampilkan tombol menu, brand, cari, dan scan (§9).

### 2.2 Inventaris view dan overlay

| Jenis | Nama | Template | Isi utama |
|---|---|---|---|
| View | SEPA Trend | `views/view_sepa.html` | Tabel kandidat Stage 2 |
| View | RSI Divergence | `views/view_rsi.html` | Tabel divergence 1D/4H |
| View | Pre-Breakout | `views/view_prebreakout.html` | Tabel kandidat breakout |
| View | Quality Setup | `views/view_quality_setup.html` | Tabel setup berkualitas |
| View | Watchlist & Journal | `views/view_watchlist.html` | Watchlist + jurnal trade |
| View | LPM & Smart Money | `views/view_lpm.html` | Chart tiga pane (eksperimental) |
| View | Signal Backtest Lab | `views/view_backtest.html` | Metrik dan hasil backtest |
| Overlay | Detail saham | `modals/modal_stock_detail.html` | Detail satu emiten |
| Overlay | Detail per screener | `modals/modal_sepa.html`, `modal_rsi.html`, `modal_prebreakout.html`, `modal_quality_setup.html` | Rincian kriteria |
| Overlay | Position Sizing | `modals/modal_position_sizing.html` | Kalkulator ukuran posisi |
| Overlay | Trade Journal | `modals/modal_trade_journal.html` | Form jurnal |
| Overlay | Command Palette | `modals/command_palette.html` | Cari emiten dan aksi (Ctrl K) |
| Halaman | Login | `login.html` | Masuk admin |

### 2.3 Dimensi

| Elemen | Nilai |
|---|---|
| Sidebar (desktop) | `260px`, sticky, tinggi `100dvh` |
| Sidebar (drawer, ≤1024px) | `min(300px, 86vw)` |
| Topbar (≤1024px) | tinggi `56px`, sticky |
| Padding konten | `24px` desktop, `16px` ≤768px |
| Lebar minimum yang didukung | `360px` |
| Jarak antar blok di main | `16px` |

---

## 3. Sistem Warna

### 3.1 Aturan pemakaian

| Peran | Token | Boleh dipakai untuk | Tidak boleh |
|---|---|---|---|
| Netral (slate) | `--bg-*`, `--border-*`, `--text-*` | Permukaan, garis, teks | |
| Aksen (lime) | `--brand-lime*`, `--btn-primary-*` | Tombol aksi utama, nav aktif, focus ring, link | Status data, angka, badge status, dekorasi |
| Status positif | `--status-confirmed-*` | Confirmed, kriteria lolos, harga naik, divergence regular | Tombol, dekorasi |
| Status peringatan | `--status-watchlist-*` | Watchlist, borderline, pasar istirahat | Tombol, dekorasi |
| Status negatif | `--status-fail-*` | Fail, kriteria gagal, harga turun, error | Tombol non-destruktif |
| Status info | `--status-info-*` | Divergence hidden, info netral | Dekorasi |

Status selalu ditulis sebagai teks juga (label badge, `aria-label`). Warna tidak pernah menjadi satu-satunya pembawa makna.

Palet aktif: netral slate + 1 aksen lime + 4 warna status semantik. Tidak ada warna lain. Semua warna di CSS wajib lewat token. Hex mentah hanya boleh ada di file token.

### 3.2 Token mode terang (default)

```css
:root,
:root[data-theme="light"] {
  color-scheme: light;

  /* Permukaan */
  --bg-primary:   #f8fafc;  /* Kanvas */
  --bg-secondary: #ffffff;  /* Kartu, sidebar, tabel, modal */
  --bg-tertiary:  #f1f5f9;  /* Hover, baris terpilih, area sunken */
  --bg-row-alt:   #fafcfd;  /* Baris tabel selang-seling */
  --bg-overlay:   rgba(15, 23, 42, 0.45);  /* Backdrop modal */

  /* Garis */
  --border-subtle:  #e2e8f0;
  --border-strong:  #cbd5e1;
  --border-control: #7b8aa0;  /* Border input, minimal 3:1 */
  --border-focus:   #4d7c0f;

  /* Teks */
  --text-primary:   #0f172a;  /* 17.9:1 di putih */
  --text-secondary: #475569;  /*  7.6:1 */
  --text-muted:     #5b6b80;  /*  5.4:1 di putih, 4.97:1 di --bg-tertiary */
  --text-inverse:   #ffffff;

  /* Aksen */
  --brand-lime:        #4d7c0f;  /* Link, ikon aktif, focus. 4.99:1 */
  --brand-lime-hover:  #3f6212;
  --brand-lime-dim:    #ecfccb;  /* Background nav aktif */
  --brand-lime-border: #bef264;
  --btn-primary-bg:    #4d7c0f;
  --btn-primary-hover: #3f6212;
  --btn-primary-text:  #ffffff;  /* 4.99:1 */

  /* Status */
  --status-confirmed-text: #15803d;  --status-confirmed-bg: #f0fdf4;  --status-confirmed-border: #bbf7d0;
  --status-watchlist-text: #b45309;  --status-watchlist-bg: #fffbeb;  --status-watchlist-border: #fde68a;
  --status-fail-text:      #b91c1c;  --status-fail-bg:      #fef2f2;  --status-fail-border:      #fecaca;
  --status-info-text:      #1d4ed8;  --status-info-bg:      #eff6ff;  --status-info-border:      #bfdbfe;

  /* Elevasi */
  --shadow-overlay: 0 8px 24px -6px rgba(15, 23, 42, 0.14), 0 2px 6px -2px rgba(15, 23, 42, 0.08);
  --shadow-modal:   0 20px 25px -5px rgba(15, 23, 42, 0.12), 0 8px 10px -6px rgba(15, 23, 42, 0.10);
}
```

### 3.3 Token mode gelap

```css
:root[data-theme="dark"] {
  color-scheme: dark;

  --bg-primary:   #0b1220;
  --bg-secondary: #111a2e;
  --bg-tertiary:  #1c2740;
  --bg-row-alt:   #0e1628;
  --bg-overlay:   rgba(2, 6, 23, 0.65);

  --border-subtle:  #1f2a40;
  --border-strong:  #2c3a55;
  --border-control: #5f6f8a;
  --border-focus:   #a3e635;

  --text-primary:   #e2e8f0;  /* 14.1:1 di --bg-secondary */
  --text-secondary: #cbd5e1;  /* 11.7:1 */
  --text-muted:     #94a3b8;  /*  6.8:1, 5.8:1 di --bg-tertiary */
  --text-inverse:   #0f172a;

  --brand-lime:        #a3e635;  /* 11.5:1 */
  --brand-lime-hover:  #bef264;
  --brand-lime-dim:    rgba(163, 230, 53, 0.12);
  --brand-lime-border: rgba(163, 230, 53, 0.35);
  --btn-primary-bg:    #84cc16;
  --btn-primary-hover: #a3e635;
  --btn-primary-text:  #0f172a;  /* 9.0:1 */

  --status-confirmed-text: #4ade80;  --status-confirmed-bg: rgba(74, 222, 128, 0.12);  --status-confirmed-border: rgba(74, 222, 128, 0.35);
  --status-watchlist-text: #fbbf24;  --status-watchlist-bg: rgba(251, 191, 36, 0.12);  --status-watchlist-border: rgba(251, 191, 36, 0.35);
  --status-fail-text:      #f87171;  --status-fail-bg:      rgba(248, 113, 113, 0.12); --status-fail-border:      rgba(248, 113, 113, 0.35);
  --status-info-text:      #60a5fa;  --status-info-bg:      rgba(96, 165, 250, 0.12);  --status-info-border:      rgba(96, 165, 250, 0.35);

  --shadow-overlay: 0 8px 24px -6px rgba(0, 0, 0, 0.5);
  --shadow-modal:   0 20px 25px -5px rgba(0, 0, 0, 0.55);
}
```

Token lama `--status-div-reg-*` menjadi alias `--status-confirmed-*`, dan `--status-div-hid-*` menjadi alias `--status-info-*`. Token `--shadow-card`, `--shadow-hover`, `--shadow-lime`, dan `--brand-lime-glow` dihapus.

### 3.4 Warna data

| Data | Aturan |
|---|---|
| RS Rating ≥ 90 | `--status-confirmed-text`, weight 700 |
| RS Rating 70-89 | `--text-primary`, weight 600 (lolos threshold) |
| RS Rating 50-69 | `--status-watchlist-text` |
| RS Rating < 50 | `--status-fail-text` |
| SEPA Score bar 8/8 | fill `--status-confirmed-text` |
| SEPA Score bar 6-7 | fill `--status-watchlist-text` |
| SEPA Score bar < 6 | fill `--status-fail-text` |
| Perubahan harga / % | naik `--status-confirmed-text`, turun `--status-fail-text`, nol `--text-secondary` |
| Kriteria C1-C8 | lolos: badge terisi warna positif; gagal: badge outline warna negatif. `aria-label="C1 lolos"` / `"C1 gagal"` |

### 3.5 Warna chart (LPM, lightweight-charts)

Chart membaca warna dari CSS variable saat dibuat, dan menerapkan ulang saat tema berganti. Tidak ada hex di JS.

| Token | Dipakai untuk |
|---|---|
| `--chart-text` | Label sumbu (= `--text-muted`) |
| `--chart-grid` | Garis grid (= `--border-subtle`) |
| `--chart-up` / `--chart-down` | Candle naik/turun (= status positif/negatif) |
| `--chart-series-1` / `--chart-series-2` | Garis LPM dan seri pembanding, didefinisikan di file token per mode |

### 3.6 Mekanisme tema

- Atribut `data-theme="light|dark"` di elemen `<html>`.
- Script kecil inline di `<head>` (`index.html` dan `login.html`) menentukan tema sebelum halaman digambar: pilihan tersimpan di `localStorage` (dibungkus `try/catch`), kalau tidak ada pakai mode terang (D-2). Ini mencegah kedip putih.
- Tombol toggle di bagian bawah sidebar (dan di drawer mobile), `aria-pressed` sesuai state, label "Mode gelap".
- Hanya nilai token yang berbeda antar mode. Komponen tidak boleh punya aturan khusus per tema, kecuali chart (§3.5).

---

## 4. Tipografi

### 4.1 Font

| Font | Dipakai untuk | Alasan |
|---|---|---|
| Plus Jakarta Sans 400/500/600/700 | Semua teks UI | Dibuat untuk identitas kota Jakarta, cocok untuk produk pasar modal Indonesia. Huruf lebar dan terbuka, tetap terbaca di 12-13px |
| JetBrains Mono 500/600 | Kode ticker, angka di tabel, kbd | Lebar karakter sama, jadi kolom ticker dan angka rata tanpa tabel bergerigi |

Weight 800 tidak dipakai lagi, supaya font yang diunduh lebih sedikit. Semua angka memakai `font-variant-numeric: tabular-nums`.

### 4.2 Skala

| Token | Size | Weight | Tracking | Dipakai untuk |
|---|---|---|---|---|
| `--text-xs` | 11px | 600 | +0.04em | Header tabel, label summary, label seksi sidebar, badge (uppercase) |
| `--text-sm` | 13px | 400/500 | normal | Isi tabel, teks pendukung |
| `--text-base` | 14px | 400 | normal | Teks default |
| `--text-md` | 16px | 600 | -0.01em | Judul seksi, judul modal |
| `--text-lg` | 20px | 700 | -0.02em | Judul view, metrik Backtest |
| `--text-xl` | 24px | 700 | -0.02em | Judul halaman login |

Line height: 1.5 untuk teks, 1.25 untuk judul. Uppercase hanya untuk ukuran `--text-xs`, tidak pernah untuk judul.

### 4.3 Ticker

```css
.ticker-code {
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.03em;
  color: var(--text-primary);
}
```

---

## 5. Spacing, Radius, Elevasi

### 5.1 Spacing

`--space-1: 4px`, `--space-2: 8px`, `--space-3: 12px`, `--space-4: 16px`, `--space-5: 20px`, `--space-6: 24px`, `--space-8: 32px`, `--space-10: 40px`.

Jarak di dalam komponen memakai 4-12px. Jarak antar blok di main memakai 16px. Jarak antar grup besar (banner ke view) memakai 24px.

### 5.2 Radius

| Token | Nilai | Dipakai untuk |
|---|---|---|
| `--radius-sm` | 4px | Badge kriteria C1-C8, kbd, skeleton |
| `--radius-md` | 6px | Tombol, input, tombol ikon |
| `--radius-lg` | 8px | Kartu tabel, banner, panel |
| `--radius-xl` | 12px | Modal, command palette |
| `--radius-pill` | 999px | Badge status dan badge jumlah saja |

### 5.3 Elevasi

| Level | Elemen | Perlakuan |
|---|---|---|
| 0 | Kartu, tabel, banner, sidebar | Border `--border-subtle`, tanpa shadow |
| 1 | Header tabel sticky, topbar | Border bawah saja |
| 2 | Dropdown, toast, command palette | `--shadow-overlay` |
| 3 | Modal | `--shadow-modal` |

Blur (`backdrop-filter`) maksimal di dua tempat: backdrop modal dan backdrop command palette.

---

## 6. Komponen

### 6.1 Sidebar

- **Brand**: 🦖 + "Tirexxz Screnner". Emoji adalah logo sementara (D-8). Ganti dengan SVG saat pemilik menyediakannya.
- **Search trigger**: membuka command palette, menampilkan `Ctrl K`.
- **Nav item**: ikon SVG 16px + label + badge jumlah. Badge berisi jumlah hasil nyata dari scan terakhir, atau `--` sebelum ada data. Tidak ada badge label seperti `CALC`, `LAB`, `NEW`.
- **Nav aktif**: background `--brand-lime-dim`, teks dan ikon `--brand-lime`, `aria-current="page"`.
- **Position Sizing**: membuka modal, jadi tampil sebagai aksi di grup Tools, tanpa badge.
- **Tombol Scan**: satu-satunya tombol primary di layar. Saat scan berjalan: disabled, label "Scanning...", progress bar dan ticker yang sedang diproses tampil di bawahnya (`aria-live="polite"`).
- **Status pasar**: titik warna statis sesuai state nyata (open = positif, break = peringatan, closed = muted) + teks. Tidak berdenyut.
- **Kuota API**: angka nyata `terpakai / 1000` + bar tipis.
- **User**: "Administrator" + tombol logout dengan konfirmasi. Tidak ada titik "Online".
- **Toggle tema** dan **versi** di paling bawah.

### 6.2 Market Regime Banner

Menampilkan kondisi IHSG (nilai, perubahan, MA50/MA200), status regime, rekomendasi alokasi modal, dan waktu update. Status regime tampil sebagai badge teks berwarna status. Background datar `--bg-secondary`, tanpa gradient dan tanpa ikon emoji. Saat memuat: placeholder `--` dan teks "Memuat kondisi IHSG...". Saat gagal: pesan error singkat + tombol "Coba lagi".

### 6.3 Summary Bar (pengganti Stats Cards)

Satu baris ringkasan di atas toolbar, berisi angka nyata dari scan terakhir:

```
DI-SCAN  847   ·   CONFIRMED  23   ·   WATCHLIST  41   ·   UPDATE  15:32 WIB
```

- Label `--text-xs` uppercase `--text-muted`, nilai `--text-md` tabular `--text-primary`.
- Nilai Confirmed dan Watchlist memakai warna status masing-masing.
- Tanpa ikon, tanpa kartu, tanpa hover. Sebelum ada data, nilai berisi `--`.
- Isi per screener mengikuti data yang memang dihasilkan screener itu. Item statis seperti "IHSG Benchmark: Aktif" dihapus.
- **Backtest** memakai komponen yang sama dengan nilai ukuran `--text-lg`, karena metrik di sana adalah hasil utama halaman.
- Di ≤480px item membungkus menjadi grid 2 kolom.

### 6.4 Toolbar

Input cari, filter, sort, dan export di atas tabel. Tinggi kontrol 36px di desktop, 44px di perangkat sentuh. Input memakai border `--border-control`.

### 6.5 Data Table

Kolom per screener mengikuti data yang ada di kode. Contoh acuan SEPA (diverifikasi ulang terhadap kode di Fase 3 rencana):

| Kolom | Rata | Catatan |
|---|---|---|
| Ticker | Kiri | Mono tebal, sticky kiri di mobile |
| Nama Perusahaan | Kiri | Terpotong dengan ellipsis, nama lengkap di `title` |
| Sektor | Kiri | `--text-secondary` |
| Harga | Kanan | `Rp 9.800`, tabular |
| SEPA Score | Tengah | Bar mini + `x/8` (§3.4) |
| Status | Tengah | Badge status |
| Kriteria C1-C8 | Tengah | 8 badge mini (§3.4) |
| RS Rating | Tengah | Warna sesuai §3.4 |
| % dari 52W Low / High | Kanan | Tabular, bertanda +/- |
| Chart | Tengah | Tombol ikon ke TradingView, `aria-label` berisi ticker |

```css
.data-table thead th {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--text-muted);
  padding: 10px 14px;
  border-bottom: 1px solid var(--border-subtle);
  background: var(--bg-secondary);
  position: sticky;
  top: 0;
}
.data-table tbody tr {
  border-bottom: 1px solid var(--border-subtle);
  transition: background-color 150ms ease;
}
.data-table tbody tr:hover,
.data-table tbody tr:focus-visible {
  background: var(--bg-tertiary);
}
.data-table tbody td {
  padding: 12px 14px;
  font-size: 13px;
  color: var(--text-secondary);
}
```

- Baris yang bisa diklik untuk membuka detail: `tabindex="0"`, Enter membuka detail, focus ring terlihat.
- Di mobile tabel discroll horizontal di dalam kartunya, halaman tidak ikut melebar.

### 6.6 Badge status

Pill kecil berisi teks: `--text-xs` uppercase, weight 600, padding `3px 10px`, warna dari set status (teks, background, border). Tanpa titik, tanpa glow. Badge hanya untuk status nyata (Confirmed, Watchlist, Fail, Regular, Hidden, dan sejenisnya).

### 6.7 Tombol

| Varian | Tampilan | Pemakaian |
|---|---|---|
| Primary | Background `--btn-primary-bg`, teks `--btn-primary-text` | Satu per layar: Scan IDX, atau aksi simpan di modal |
| Secondary | Background `--bg-secondary`, border `--border-strong`, teks `--text-primary` | Aksi lain |
| Ghost / ikon | Transparan, ikon `--text-secondary`, 32px (44px di layar sentuh) | Tutup, refresh, link TradingView |
| Destruktif | Teks `--status-fail-text`, border status negatif | Hapus entri jurnal, logout |

State: hover mengubah background/border (150ms), active memakai warna hover yang lebih gelap, disabled `opacity: 0.5` + `cursor: not-allowed`, focus outline 2px `--border-focus` offset 2px. Tidak ada `translateY`, `scale`, atau shadow saat hover.

Panah (`→`) tidak dipakai sebagai hiasan tombol.

### 6.8 Modal

- `role="dialog"`, `aria-modal="true"`, `aria-labelledby` ke judul modal.
- Saat dibuka: fokus pindah ke elemen pertama yang bisa difokus, Tab berputar di dalam modal.
- Tutup dengan Escape, tombol tutup, atau klik backdrop. Fokus kembali ke elemen pemicu.
- Satu helper modal bersama dipakai semua modal, bukan fungsi tutup terpisah per screener.
- Di ≤480px modal tampil layar penuh.
- Konten Position Sizing yang sekarang berbentuk "bento" ditata ulang sebagai daftar hasil hitungan (label + nilai), karena isinya angka berurutan, bukan kartu dengan ukuran berbeda.

### 6.9 Command Palette

Mengikuti aturan modal. Hasil dapat dipilih dengan panah atas/bawah dan Enter. Ikon hasil memakai SVG, bukan emoji.

### 6.10 Toast

`role="status"` (`role="alert"` untuk error), hilang sendiri setelah 4 detik, bisa ditutup. Di ≤480px tampil selebar layar di bawah.

### 6.11 Ikon

- SVG inline, stroke 2px, `currentColor`, 16px di nav dan tombol, 14px inline. Geometri mengikuti SVG yang sudah ada di kode, supaya satu set konsisten dan tetap tajam di 16px.
- Setiap ikon harus mewakili maknanya. Pemetaan nav:

| Item | Ikon |
|---|---|
| SEPA Trend | garis tren naik |
| RSI Divergence | garis osilator (activity) |
| Pre-Breakout | target / crosshair |
| Quality Setup | centang dalam perisai |
| Watchlist & Journal | bookmark |
| LPM & Smart Money | bar chart |
| Position Sizing | sliders |
| Signal Backtest Lab | jam berputar balik (history) |

- Ikon dekoratif memakai `aria-hidden="true"`. Tombol yang hanya berisi ikon wajib punya `aria-label`.
- Emoji tidak dipakai di UI, kecuali logo sementara (D-8).

---

## 7. State Data (wajib di setiap view)

Setiap view yang menampilkan data punya tiga state, masing-masing menyebut penyebab dan langkah berikutnya.

| State | Isi | Contoh teks (sesuaikan per view) |
|---|---|---|
| Loading | Skeleton baris tabel, `aria-busy="true"` pada tabel, teks untuk pembaca layar | "Memuat hasil SEPA Trend..." |
| Kosong: belum pernah scan | Penjelasan + tombol primary | "Belum ada hasil scan. Jalankan Scan IDX untuk mengisi tabel ini." [Scan IDX Sekarang] |
| Kosong: hasil filter | Penjelasan + aksi reset | "Tidak ada saham yang cocok dengan filter ini." [Reset filter] |
| Error | Pesan dari server + aksi ulang | "Gagal memuat hasil SEPA Trend: {pesan}." [Coba lagi] |

Ikon emoji di empty state dihapus. Kalau perlu tanda visual, pakai ikon SVG yang relevan.

---

## 8. Motion (MOTION 1)

| Boleh | Durasi | Tujuan |
|---|---|---|
| Transisi warna background/border/teks | 150ms ease | Feedback hover dan focus |
| Modal dan command palette muncul (opacity + scale 0.98 ke 1) | 150ms | Menunjukkan lapisan baru |
| Toast masuk | 200ms | Menarik perhatian ke notifikasi |
| Skeleton shimmer | selama loading saja | Menandai data sedang dimuat |
| Progress bar scan | mengikuti progres | Menunjukkan kemajuan scan |
| Spinner di tombol scan | selama scan | Menunjukkan proses berjalan |
| Fade-in baris tabel | 200ms, jeda 20ms per baris, total maks 300ms | Hanya saat hasil scan pertama kali tampil (D-4) |

**Dilarang**: `transform` saat hover, animasi `infinite` di luar state loading (radar ping, denyut hati, pulse glow), `transition: all`.

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

---

## 9. Responsif

| Lebar | Perilaku |
|---|---|
| ≥ 1025px | Sidebar permanen 260px, konten di kanan |
| ≤ 1024px | Sidebar jadi drawer (backdrop, tutup dengan Escape atau klik backdrop), topbar 56px tampil |
| ≤ 768px | Padding konten 16px, toolbar menumpuk, market regime banner menumpuk vertikal |
| ≤ 480px | Summary bar grid 2 kolom, modal layar penuh, toast selebar layar |
| 360px | Lebar minimum yang diuji |

Aturan wajib:
- Tidak ada scroll horizontal di level halaman pada lebar berapa pun ≥ 360px.
- Tabel scroll horizontal di dalam kartunya. Kolom ticker sticky di kiri.
- Target sentuh minimal 44×44px di `(pointer: coarse)`.
- Topbar berisi tombol menu, brand, tombol cari, dan tombol scan, semuanya ikon SVG dengan `aria-label`.

---

## 10. Aksesibilitas

- Kontras WCAG AA: teks normal ≥ 4.5:1, teks besar ≥ 3:1, border kontrol dan ikon ≥ 3:1. Nilai di §3.2 dan §3.3 sudah dicek untuk dua mode.
- Focus terlihat di semua elemen interaktif. `outline: none` hanya boleh kalau diganti indikator lain yang sama jelasnya.
- Semua yang bisa diklik adalah `<button>` atau `<a>`. Baris tabel yang bisa diklik memakai `tabindex="0"` + handler Enter.
- Escape menutup modal, command palette, dan drawer.
- `aria-live="polite"` untuk progres scan dan toast.
- `lang="id"` di elemen `<html>`.

---

## 11. Copy

- Bahasa Indonesia. Istilah teknis trading tetap dalam bentuk aslinya (SEPA, RS Rating, Stage 2, Breakout).
- Tidak ada em dash. Pakai titik dua, koma, titik, atau tanda kurung.
- Tidak ada emoji di teks UI.
- Label tombol menyebut aksinya: "Scan IDX Sekarang", "Buka Detail", "Simpan ke Jurnal", "Reset filter".
- Angka hanya dari data nyata. Sebelum ada data, tampilkan `--`.
- Format judul tab: `Tirexxz Screnner: SEPA Trend, RSI Divergence & Pre-Breakout`.

---

## 12. Pola yang Dihindari

| Pola | Aturan pengganti | Rule antislop |
|---|---|---|
| Emoji sebagai ikon nav, tombol, dan judul | Ikon SVG yang relevan, atau tanpa ikon | R-04 |
| Hover yang menggeser elemen | Perubahan warna saja | R-19 |
| Animasi berulang terus (radar, denyut, glow) | Titik statis sesuai state nyata | R-19 |
| Gradient dan shadow di setiap kartu | Kartu datar dengan border | R-01, R-12 |
| Badge label tanpa fungsi (`CALC`, `LAB`, `NEW`) | Hapus, atau ganti angka nyata | R-09 |
| Titik "Online" yang tidak menandai apa-apa | Hapus | R-31 |
| Deretan stat card berikon | Summary Bar | C-3 |
| Teks abu-abu yang tidak terbaca | `--text-muted` yang lolos 4.5:1 | R-25 |
| Hex mentah di file komponen | Token saja | R-29 |
| Kontrol hanya bisa dipakai dengan mouse | Button/link asli, Escape, focus terlihat | R-32 |

---

## 13. Referensi Inspirasi

Referensi ini untuk menilai arah, bukan untuk ditiru.

- **Bloomberg Terminal, Refinitiv Eikon**: kepadatan data, tabel sebagai pusat layar.
- **TradingView**: kode warna status dan perubahan harga.
- **Linear**: kejelasan sidebar dan command palette.
