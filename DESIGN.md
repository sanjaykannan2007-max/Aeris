# AERIS Design System (DESIGN.md)

**Product Name:** AERIS  
**Full Title:** Aircraft Engine Reliability & Intelligence System  
**Tagline:** Predict. Diagnose. Prevent.  
**Visual Aesthetic:** Mission-Control Aerospace Operations Center (Bloomberg Terminal meets Aerospace Engineering)

---

## 1. Brand & Design Principles

1. **Precision & Engineering Rigor**: Information density is maximized without visual clutter. Data alignment, numeric readability, and clear unit labels take priority.
2. **Restrained Semantic Color**: Color is strictly functional. Bright colors are reserved for status alerts (`HEALTHY`, `MONITOR`, `WARNING`, `CRITICAL`), threshold breaches, and key interactive focal points.
3. **High Contrast Dark Palette**: Built on deep navy/graphite backgrounds with subtle translucency and low-contrast grid boundaries to reduce eye fatigue during continuous monitoring.
4. **Safety & Transparency**: All predictions display model confidence, range bounds, and explicit risk indicators. Simulated or demo records are prominently labeled `DEMO / SIMULATED`.

---

## 2. Color System

### Base & Background Tokens
- `--bg-canvas`: `#070a10` (Deep aerospace space/navy base)
- `--bg-sidebar`: `#0b0f19` (Dark graphite navigation base)
- `--bg-panel`: `rgba(15, 23, 42, 0.85)` (Translucent slate glass surface)
- `--bg-panel-solid`: `#0f172a` (Solid slate panel background)
- `--bg-card`: `#1e293b` (Elevated card background)
- `--bg-card-hover`: `#334155` (Interactive card highlight)

### Border & Divider Tokens
- `--border-subtle`: `rgba(255, 255, 255, 0.08)` (Subtle grid dividers)
- `--border-default`: `rgba(255, 255, 255, 0.14)` (Standard panel border)
- `--border-accent`: `rgba(56, 189, 248, 0.4)` (Cyan highlight border)

### Typography Tokens
- `--text-primary`: `#f8fafc` (High readability white)
- `--text-secondary`: `#94a3b8` (Muted technical text)
- `--text-muted`: `#64748b` (Disabled/label text)

### Semantic Status Colors
- **HEALTHY** (Green): `#10b981` (Glow: `rgba(16, 185, 129, 0.25)`)
- **MONITOR** (Blue/Sky): `#0284c7` (Glow: `rgba(2, 132, 199, 0.25)`)
- **WARNING** (Amber): `#f59e0b` (Glow: `rgba(245, 158, 11, 0.25)`)
- **CRITICAL** (Red): `#ef4444` (Glow: `rgba(239, 68, 68, 0.3)`)
- **UNKNOWN BEHAVIOUR** (Purple): `#a855f7` (Glow: `rgba(168, 85, 247, 0.3)`)
- **MODEL DISAGREEMENT** (Orange): `#f97316` (Glow: `rgba(249, 115, 22, 0.3)`)

---

## 3. Typography & Numeric Styling

### Font Families
- **Display & Headings**: `'Outfit'`, `'Inter'`, sans-serif (Strong, compact aerospace branding)
- **Body & UI**: `'Inter'`, system-ui, sans-serif
- **Data & Telemetry**: `'JetBrains Mono'`, monospace (Tabular numeric alignment for RUL, Cycles, Sensor Z-scores, Engine IDs)

### Type Scale
| Role | Font Size | Line Height | Weight | Letter Spacing |
| :--- | :--- | :--- | :--- | :--- |
| Brand Header | `1.5rem` (`24px`) | `1.2` | `800` | `+0.05em` |
| Page Title | `1.25rem` (`20px`)| `1.3` | `700` | `+0.02em` |
| Section Header | `1.0rem` (`16px`) | `1.4` | `600` | `normal` |
| Body Text | `0.875rem` (`14px`)| `1.5` | `400` | `normal` |
| Small Label | `0.75rem` (`12px`) | `1.4` | `500` | `+0.03em` |
| KPI Metric Value | `2.0rem` (`32px`) | `1.1` | `700 (Mono)` | `normal` |

---

## 4. Spacing, Radius & Elevation

### Spacing Scale
`4px` (xs), `8px` (sm), `12px` (md), `16px` (lg), `24px` (xl), `32px` (2xl)

### Corner Radius
- `--radius-sm`: `4px` (Table cells, status tags, badge pills)
- `--radius-md`: `6px` (Cards, buttons, inputs)
- `--radius-lg`: `10px` (Modals, main container panels)

### Elevation & Shadows
- **Card Shadow**: `0 4px 12px rgba(0, 0, 0, 0.4)`
- **Panel Inset**: `inset 0 1px 1px rgba(255, 255, 255, 0.05)`
- **Glow Accents**: `0 0 12px <status_color_rgba>`

---

## 5. UI Component Specifications

### 1. Navigation & Header
- Left Sidebar with mission-control hierarchy:
  - `COMMAND CENTER` (`Overview`, `Fleet`, `Aircraft`, `Engines`)
  - `MONITORING` (`Live Telemetry`, `C-MAPSS Replay`, `Diagnostics`, `Alerts`)
  - `MAINTENANCE` (`Maintenance Control`, `Work Orders`, `History`)
  - `INTELLIGENCE` (`Analytics`, `Model Performance`, `What-If Simulator`)
  - `SYSTEM` (`Reports`, `Users`, `Settings`)
- Top bar with real-time dataset switcher, backend status indicator, notification bell, global search trigger (`Ctrl + K`), and current user profile badge.

### 2. Metric Cards & Status Badges
- High-density KPI cards featuring icon badge, bold tabular metric value, delta indicator, and descriptive technical subtext.
- Status badges use pill shapes (`padding: 2px 8px`, `border-radius: 4px`, uppercase monospaced text).

### 3. Data Tables & Sensor Feeds
- Compact table rows (`padding: 8px 12px`).
- Monospaced alignment for numerical columns (Cycles, RUL, Anomaly scores).
- Hover state highlights row with subtle cyan glow border.

### 4. Interactive Charts
- Dark-themed Chart.js lines with area fills (`alpha: 0.15`), crisp gridlines (`rgba(255,255,255,0.05)`), and custom tooltip popups formatted in technical monospaced text.

### 5. Telemetry Replay & Simulator Controls
- Media-style playback bar (Play, Pause, Reset, 1X, 2X, 5X, 10X speed sliders).
- Cycle progress slider with step markers: `HEALTHY` -> `DEGRADATION ONSET` -> `MONITOR` -> `WARNING` -> `CRITICAL`.

### 6. Modal & Command Palette (`Ctrl + K`)
- Overlay backdrop blur (`backdrop-filter: blur(8px)`).
- Instant fuzzy-search command palette listing page navigation, engine search, alert filters, and simulation triggers.

---

## 6. Accessibility & State Definitions

- **Color Contrast**: All text elements meet AA standards against dark background tokens (`>= 4.5:1`).
- **Keyboard Navigation**: Full tab index support for forms, data tables, playback controls, and modal dialogs.
- **States**:
  - **Loading**: Skeleton pulse shimmer and centered monospaced spinner (`Loading telemetry...`).
  - **Empty State**: Clear icon, concise technical message (`No active work orders for Engine AE-2042-L`), and primary action button.
  - **Error State**: Red bordered container with retry action button and technical details log.
