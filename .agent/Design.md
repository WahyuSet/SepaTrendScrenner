# Design System — IDX SEPA Trend Screener
**Frontend Design Document**
**Versi**: 1.0
**Tanggal**: 2026-09-01
**Referensi Skill**: enterprise-frontend-design

---

## 1. Filosofi Desain

Antarmuka IDX SEPA Trend Screener dirancang dengan prinsip **"Enterprise Clear"** — bersih, padat informasi, dan terasa premium tanpa mengorbankan keterbacaan data. Inspirasi visual: Bloomberg Terminal, Refinitiv Eikon, dan TradingView Pro.

**Prinsip utama:**
- **Data First** — setiap elemen UI melayani informasi, bukan sekadar dekorasi
- **Zero Ambiguity** — status saham (CONFIRMED/WATCHLIST) harus terlihat dalam hitungan detik
- **Tactile & Responsive** — setiap elemen interaktif memberikan feedback visual yang jelas
- **No Placeholders** — semua teks dan data adalah konten nyata

---

## 2. Layout Struktur

### 2.1 Tipe Layout: Sidebar + Main Content

```
┌──────────────────────────────────────────────────────┐
│  [Sidebar Kiri — 260px sticky]  │  [Konten Utama]    │
│                                  │                    │
│  • Logo + Tagline                │  • Stats Cards     │
│  • Tombol "Scan Sekarang"        │  • Filter Bar      │
│  • Info Last Scan                │  • Data Table      │
│  • Filter Slider (Score)         │                    │
│  • Separator                     │                    │
│  • Parameter SEPA (readonly)     │                    │
│  • Footer (versi)                │                    │
└──────────────────────────────────────────────────────┘
```

### 2.2 Dimensi & Breakpoint

| Elemen | Nilai |
|--------|-------|
| Sidebar width | `260px` (fixed) |
| Main content | `calc(100vw - 260px)` |
| Max table width | `100%` (fluid) |
| Min supported width | `1024px` (desktop-only) |
| Content padding | `24px` |
| Card gap | `16px` |

---

## 3. Color System (CSS Design Tokens — Enterprise Clear White)

Seluruh warna didefinisikan sebagai CSS Custom Properties untuk konsistensi, clean light theme, dan keterbacaan data maksimal:

```css
:root {
  /* === BACKGROUNDS === */
  --bg-primary:      #f8fafc;              /* Canvas bg: slate-50 */
  --bg-secondary:    #ffffff;              /* Cards & Sidebar: pure white */
  --bg-tertiary:     #f1f5f9;              /* Hover & Interactive: slate-100 */
  --bg-table-alt:    #fafcfd;              /* Alternating table row */

  /* === BORDERS === */
  --border-subtle:   #e2e8f0;              /* Crisp slate-200 */
  --border-focus:    #4d7c0f;              /* Lime focus ring */
  --border-strong:   #cbd5e1;              /* Slate-300 */

  /* === TYPOGRAPHY === */
  --text-primary:    #0f172a;              /* Slate-900: sharp & high-contrast */
  --text-secondary:  #334155;              /* Slate-700 */
  --text-muted:      #64748b;              /* Slate-500 */
  --text-inverse:    #ffffff;              /* White on buttons */

  /* === BRAND / LIME ACCENT === */
  --brand-lime:       #4d7c0f;              /* Lime-700: dark rich lime for crisp readability */
  --brand-lime-hover: #3f6212;              /* Lime-800 */
  --brand-lime-bright:#65a30d;              /* Lime-600 */
  --brand-lime-dim:   #ecfccb;              /* Lime-100 for badge backgrounds */
  --brand-lime-border:#bef264;              /* Lime-300 */
  --brand-lime-glow:  rgba(101, 163, 13, 0.25);

  /* === STATUS COLORS === */
  --status-confirmed-text:   #15803d;       /* Emerald-700 */
  --status-confirmed-bg:     #f0fdf4;       /* Emerald-50 */
  --status-confirmed-border: #86efac;       /* Emerald-300 */

  --status-watchlist-text:   #b45309;       /* Amber-700 */
  --status-watchlist-bg:     #fffbeb;       /* Amber-50 */
  --status-watchlist-border: #fde68a;       /* Amber-200 */

  --status-fail-text:        #b91c1c;       /* Red-700 */
  --status-fail-bg:          #fef2f2;       /* Red-50 */
  --status-fail-border:      #fecaca;       /* Red-200 */

  /* === SHADOWS === */
  --shadow-card:  0 1px 3px 0 rgba(0, 0, 0, 0.05), 0 1px 2px -1px rgba(0, 0, 0, 0.05);
  --shadow-hover: 0 6px 16px -2px rgba(0, 0, 0, 0.08), 0 2px 6px -2px rgba(0, 0, 0, 0.04);
  --shadow-lime:  0 2px 10px rgba(77, 124, 15, 0.25);
  --shadow-modal: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1);
}
```

---

## 4. Typography System

### 4.1 Font Family

```css
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap');

:root {
  --font-sans: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif;
  --font-mono: 'JetBrains Mono', 'Fira Code', monospace; /* untuk ticker codes */
}

body {
  font-family: var(--font-sans);
  font-size: 14px;
  line-height: 1.6;
  -webkit-font-smoothing: antialiased;
}
```

### 4.2 Type Scale

| Token | Size | Weight | Letter-Spacing | Digunakan untuk |
|-------|------|--------|----------------|-----------------|
| `--text-xs` | 11px | 600 | +0.05em | Label uppercase, badge |
| `--text-sm` | 13px | 400/500 | normal | Table body, subtext |
| `--text-base` | 14px | 400 | normal | Body text default |
| `--text-md` | 16px | 600 | -0.01em | Section heading |
| `--text-lg` | 20px | 700 | -0.02em | Stats card number |
| `--text-xl` | 24px | 700 | -0.02em | App title/logo |

### 4.3 Ticker Font

Kode ticker saham menggunakan **monospace** agar rapi di tabel:
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

## 5. Layout Components

### 5.1 Sidebar

```
┌─────────────────────┐
│  ◈ IDX SEPA         │  ← Logo teks (lime accent untuk "SEPA")
│    Screener         │  ← Nama app bold
│  Minervini Template │  ← Tagline: text-muted, text-xs
│                     │
│  ─────────────────  │  ← Separator subtle
│                     │
│  [▶ Scan Sekarang ] │  ← CTA Button (lime bg, dark text)
│                     │
│  Last scan:         │  ← text-muted, text-xs
│  01 Sep 2026 15:32  │  ← text-secondary
│                     │
│  ─────────────────  │
│                     │
│  Min. Score         │  ← Label uppercase
│  ████░░░░  6/8      │  ← Custom slider (lime track)
│                     │
│  ─────────────────  │
│                     │
│  SEPA Parameters    │  ← Collapsible section
│  MA 50/150/200      │
│  52W Low: 25%       │
│  52W High: 25%      │
│  RS Threshold: 70   │
│                     │
│  ─────────────────  │
│                     │
│  v1.0 · IDX · 2026  │  ← Footer text-muted
└─────────────────────┘
```

**Sidebar CSS Rules:**
- `width: 260px`, `position: sticky`, `top: 0`, `height: 100vh`
- `background: var(--bg-primary)`, `border-right: 1px solid var(--border-subtle)`
- `overflow-y: auto` dengan custom scrollbar tipis

### 5.2 Stats Cards (Summary Row)

4 kartu horizontal di bagian atas konten utama:

| Card | Icon | Label | Value |
|------|------|-------|-------|
| Total Scanned | 🔍 | TOTAL SCANNED | `847` |
| CONFIRMED | ✓ | STAGE 2 CONFIRMED | `23` (lime) |
| WATCHLIST | ~ | WATCHLIST | `41` (amber) |
| Last Updated | 🕐 | LAST SCAN | `15:32 WIB` |

**Card Style:**
```css
.stat-card {
  background: var(--bg-secondary);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}
.stat-card:hover {
  border-color: var(--border-strong);
  transform: translateY(-1px);
  box-shadow: var(--shadow-hover);
}
.stat-card .label {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--text-muted);
}
.stat-card .value {
  font-size: 28px;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--text-primary);
}
.stat-card.confirmed .value { color: var(--status-confirmed-text); }
.stat-card.watchlist .value { color: var(--status-watchlist-text); }
```

---

## 6. Data Table Design

### 6.1 Kolom Tabel

| # | Header | Alignment | Min Width | Notes |
|---|--------|-----------|-----------|-------|
| 1 | Ticker | Left | 80px | Monospace font, bold |
| 2 | Nama Perusahaan | Left | 200px | truncate dengan ellipsis |
| 3 | Sektor | Left | 120px | text-secondary |
| 4 | Harga | Right | 90px | Format: `Rp 9.800` |
| 5 | SEPA Score | Center | 90px | Mini progress bar + `x/8` |
| 6 | Status | Center | 130px | Pill badge |
| 7 | Kriteria (C1-C8) | Center | 160px | 8 Mini Pill Badges [1]..[8] (Hijau = PASS, Merah = FAIL) |
| 8 | RS Rating | Center | 80px | Color-coded number |
| 9 | % 52W Low | Right | 90px | Selalu positif `+xx.x%` |
| 10 | % 52W High | Right | 90px | Jarak dari high `-xx.x%` |
| 11 | Chart | Center | 60px | Icon button TradingView |

### 6.2 Table CSS Rules

```css
.data-table {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
}
.data-table thead th {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--text-muted);
  padding: 10px 14px;
  border-bottom: 1px solid var(--border-subtle);
  background: var(--bg-secondary);
  position: sticky;
  top: 0;
  z-index: 10;
}
.data-table tbody tr {
  border-bottom: 1px solid var(--border-subtle);
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}
.data-table tbody tr:hover {
  background: var(--bg-tertiary);
  transform: translateX(2px);
}
.data-table tbody td {
  padding: 12px 14px;
  font-size: 13px;
  color: var(--text-secondary);
}
```

### 6.3 SEPA Score Mini Progress Bar

```css
/* Kolom score: "██████░░ 6/8" */
.score-bar {
  display: flex;
  align-items: center;
  gap: 8px;
}
.score-track {
  width: 48px;
  height: 4px;
  background: var(--bg-tertiary);
  border-radius: 2px;
  overflow: hidden;
}
.score-fill {
  height: 100%;
  border-radius: 2px;
  background: var(--brand-lime);
  /* width diset via inline style: calc(score/8 * 100%) */
}
/* Score 8/8: lime, 6-7: amber, <6: red */
```

---

## 7. Status Badge Components

### 7.1 CONFIRMED Badge
```css
.badge-confirmed {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 10px;
  border-radius: 999px; /* pill shape */
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--status-confirmed-text);
  background: var(--status-confirmed-bg);
  border: 1px solid var(--status-confirmed-border);
}
```

### 7.2 WATCHLIST Badge
```css
.badge-watchlist {
  /* sama struktur, ganti warna: */
  color: var(--status-watchlist-text);
  background: var(--status-watchlist-bg);
  border: 1px solid var(--status-watchlist-border);
}
```

### 7.3 RS Rating Color Coding
| RS Score | Warna | Makna |
|----------|-------|-------|
| >= 90 | `var(--brand-lime)` | Excellent |
| 70–89 | `hsl(77, 60%, 55%)` | Good (meets threshold) |
| 50–69 | `var(--status-watchlist-text)` | Borderline |
| < 50 | `var(--status-fail-text)` | Weak |

---

## 8. Interactive Components

### 8.1 Scan Button (Primary CTA)

```css
.btn-scan {
  width: 100%;
  padding: 12px 20px;
  background: var(--brand-lime);
  color: var(--text-inverse);
  border: none;
  border-radius: 8px;
  font-family: var(--font-sans);
  font-size: 14px;
  font-weight: 700;
  letter-spacing: -0.01em;
  cursor: pointer;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}
.btn-scan:hover {
  background: var(--btn-primary-hover);
  transform: translateY(-1px);
  box-shadow: var(--shadow-lime);
}
.btn-scan:active {
  transform: scale(0.98);
}
.btn-scan:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
}
```

### 8.2 Score Slider (Filter)

```css
.score-slider {
  -webkit-appearance: none;
  width: 100%;
  height: 4px;
  border-radius: 2px;
  background: linear-gradient(
    to right,
    var(--brand-lime) 0%,
    var(--brand-lime) calc(var(--pct, 75%) ),
    var(--bg-tertiary) calc(var(--pct, 75%))
  );
  outline: none;
}
.score-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: var(--brand-lime);
  cursor: pointer;
  border: 2px solid var(--bg-primary);
  box-shadow: 0 0 0 3px var(--brand-lime-glow);
  transition: box-shadow 0.2s;
}
.score-slider:hover::-webkit-slider-thumb {
  box-shadow: 0 0 0 6px var(--brand-lime-glow);
}
```

### 8.3 TradingView Link Button

```css
.btn-tv {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 6px;
  background: transparent;
  border: 1px solid var(--border-subtle);
  color: var(--text-muted);
  text-decoration: none;
  transition: all 0.2s ease;
}
.btn-tv:hover {
  background: hsl(210, 100%, 60%, 0.1);
  border-color: hsl(210, 100%, 60%);
  color: hsl(210, 100%, 60%);
  transform: translateY(-1px);
}
/* Icon: external-link SVG 14px */
```

---

## 9. Loading State — Skeleton Shimmer

Saat scan berlangsung, tabel diganti dengan **skeleton loader** animasi shimmer (bukan spinner).

```css
@keyframes shimmer {
  0%   { background-position: -600px 0; }
  100% { background-position: 600px 0; }
}

.skeleton {
  background: linear-gradient(
    90deg,
    var(--bg-secondary) 25%,
    var(--bg-tertiary)  50%,
    var(--bg-secondary) 75%
  );
  background-size: 600px 100%;
  animation: shimmer 1.5s infinite linear;
  border-radius: 4px;
}

/* Contoh penggunaan: */
.skeleton-row {
  display: flex;
  gap: 16px;
  padding: 14px;
  border-bottom: 1px solid var(--border-subtle);
}
.skeleton-ticker  { width: 60px;  height: 14px; }
.skeleton-name    { width: 180px; height: 14px; }
.skeleton-price   { width: 70px;  height: 14px; }
.skeleton-badge   { width: 100px; height: 22px; border-radius: 999px; }
```

---

## 10. Row Fade-In Animation

Saat data tabel muncul setelah scan selesai, setiap baris muncul dengan fade-in stagger ringan.

```css
@keyframes fadeInRow {
  from {
    opacity: 0;
    transform: translateY(6px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.data-table tbody tr {
  animation: fadeInRow 0.3s cubic-bezier(0.4, 0, 0.2, 1) both;
}

/* Stagger via JS: set style="animation-delay: Xms" per row */
/* delay = index * 30ms, max 600ms */
```

---

## 11. Sidebar Parameter Panel (Readonly Info)

Menampilkan parameter SEPA yang digunakan saat scan terakhir (readonly, informatif):

```
PARAMETER AKTIF          ← uppercase label
─────────────────
MA Type        SMA
MA Periods     50 / 150 / 200
52W Lookback   252 hari
Min 52W Low    25%
Max 52W High   25%
RS Threshold   70
Benchmark      IHSG (^JKSE)
```

Style: monospace untuk value, `text-muted` untuk key, border-bottom per item.

---

## 12. Responsiveness

Aplikasi ini adalah **desktop-only** (minimum 1024px). Tidak ada mobile layout.
Tabel menggunakan `overflow-x: auto` pada container-nya untuk mencegah breakage di layar 1024px.

---

## 13. Anti-Patterns yang Dihindari

Sesuai enterprise-frontend-design skill:

| Anti-Pattern | Keputusan |
|---|---|
| Generic card rows 3-in-a-row dengan icon lorem | ❌ Diganti stats cards dengan data nyata |
| Loading spinner plain | ❌ Diganti skeleton shimmer |
| Tailwind default gradients purple-to-blue | ❌ Menggunakan HSL tokens kustom |
| Button tanpa hover/active state | ❌ Semua button punya full interaction states |
| Flat interaction (tidak ada feedback) | ❌ Semua row/card punya hover + translateY |
| Placeholder teks "John Doe" / "Lorem ipsum" | ❌ Semua konten domain-specific (ticker IDX nyata) |

---

## 14. Referensi Visual Inspirasi

- **Bloomberg Terminal** — sidebar kiri, data tabel padat, teks putih di gelap
- **TradingView Pro** — color coding status, badge status, dark theme
- **Refinitiv Eikon** — enterprise layout, informasi dense tanpa noise
- **Linear.app** — micro-interactions halus, sidebar clean
