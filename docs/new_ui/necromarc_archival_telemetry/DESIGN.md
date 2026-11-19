---
name: NecroMARC Archival Telemetry
colors:
  surface: '#141316'
  surface-dim: '#141316'
  surface-bright: '#3a383c'
  surface-container-lowest: '#0f0e11'
  surface-container-low: '#1c1b1e'
  surface-container: '#201f22'
  surface-container-high: '#2b292d'
  surface-container-highest: '#363437'
  on-surface: '#e6e1e5'
  on-surface-variant: '#d0c5af'
  inverse-surface: '#e6e1e5'
  inverse-on-surface: '#313033'
  outline: '#99907c'
  outline-variant: '#4d4635'
  surface-tint: '#e9c349'
  primary: '#f2ca50'
  on-primary: '#3c2f00'
  primary-container: '#d4af37'
  on-primary-container: '#554300'
  inverse-primary: '#735c00'
  secondary: '#d7ffc5'
  on-secondary: '#053900'
  secondary-container: '#2ff801'
  on-secondary-container: '#0f6d00'
  tertiary: '#e3c2ff'
  on-tertiary: '#490080'
  tertiary-container: '#d09eff'
  on-tertiary-container: '#6700b0'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#ffe088'
  primary-fixed-dim: '#e9c349'
  on-primary-fixed: '#241a00'
  on-primary-fixed-variant: '#574500'
  secondary-fixed: '#79ff5b'
  secondary-fixed-dim: '#2ae500'
  on-secondary-fixed: '#022100'
  on-secondary-fixed-variant: '#095300'
  tertiary-fixed: '#f0dbff'
  tertiary-fixed-dim: '#ddb7ff'
  on-tertiary-fixed: '#2c0051'
  on-tertiary-fixed-variant: '#6900b3'
  background: '#141316'
  on-background: '#e6e1e5'
  surface-variant: '#363437'
typography:
  display-lg:
    fontFamily: EB Garamond
    fontSize: 48px
    fontWeight: '500'
    lineHeight: 56px
    letterSpacing: -0.01em
  display-lg-mobile:
    fontFamily: EB Garamond
    fontSize: 34px
    fontWeight: '500'
    lineHeight: 40px
  headline-lg:
    fontFamily: EB Garamond
    fontSize: 32px
    fontWeight: '500'
    lineHeight: 38px
  headline-md:
    fontFamily: EB Garamond
    fontSize: 24px
    fontWeight: '500'
    lineHeight: 32px
  headline-sm:
    fontFamily: EB Garamond
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  title-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 24px
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 26px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 22px
  body-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 18px
  code-md:
    fontFamily: IBM Plex Mono
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 20px
  code-sm:
    fontFamily: IBM Plex Mono
    fontSize: 11px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.05em
  label-md:
    fontFamily: IBM Plex Sans
    fontSize: 13px
    fontWeight: '500'
    lineHeight: 18px
    letterSpacing: 0.03em
  label-sm:
    fontFamily: IBM Plex Sans
    fontSize: 11px
    fontWeight: '600'
    lineHeight: 14px
    letterSpacing: 0.06em
spacing:
  gutter: 1.5rem
  gutter-mobile: 0.75rem
  margin: 2.5rem
  margin-mobile: 1rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2.5rem
---

## Brand & Style
The design system bridges historical literary preservation and cybernetic forensic science. Designed for digital archivists, cataloguers, humanities scholars, and forensic computing specialists, the product turns legacy ISO 2709 flat-file library records into resurrected, machine-readable intelligence.

The visual style blends **Dark Archival Luxury** with **Retro-Phosphor Telemetry**:
- **Atmospheric solemnity:** The UI feels like an illuminated manuscript viewed inside a darkroom observatory. Heavy obsidian surfaces are framed by antique gold hair-lines, giving bibliographic entities weight, provenance, and reverence.
- **Forensic precision:** Dynamic data points—vitality bars, MARC 21 field telemetry, corruption states, and resurrection provenance—glow with phosphor vibrancy reminiscent of terminal diagnostics.
- **Tone:** Academic, haunting, exact, and scholarly. It eschews generic tech minimalism in favor of literary depth and tactile, archival richness.

## Colors
The palette is built strictly around deep obsidian depth, illuminated parchment legibility, and high-visibility forensic indicators.

### Core Palette
- **Base Canvas (`#0D0C0F`):** Deep Obsidian Ink. Non-reflective ground layer providing absolute contrast for amber and phosphor traces.
- **Elevated Surfaces (`#15131A`):** Tonal card layers with faint spectral violet undertones, creating dimensional separation without artificial blur.
- **Primary / Gilding (`#D4AF37`):** Antique Gold. Used for brand headers, active tab borders, field labels, and formal borders at `30%` opacity (`rgba(212, 175, 55, 0.3)`).
- **Secondary / Phosphor Vitality (`#39FF14`):** CRT green. Reserved for high record health, active network nodes, operational terminal readouts, and full-vitality telemetry bars.
- **Tertiary / Resurrection Violet (`#A855F7`):** AI provenance markers, semantic vector relationships, and automated metadata synthesis tags.
- **Decay Crimson (`#EF4444`):** Data corruption alerts, missing mandatory fields (008, 245, 100), broken character encoding indicators, and record structural decay.
- **Terminal Backdrop (`#080C0A`):** Green-tinted pitch black used behind raw MARC 21 field inspector panes and terminal viewports.
- **Body & Text Neutral (`#F3EFE6`):** Warm Parchment. Replaces sterile cool white to evoke aged rag paper under warm tungsten illumination. Muted variant sits at `#A39E93` for metadata descriptions and auxiliary labels.

## Typography
The system coordinates three distinct type voices to establish clear hierarchy between narrative curation, interface mechanics, and raw data interchange:

1. **EB Garamond (Editorial / Display):** Evokes centuries of master printing, classical folio incunabula, and authoritative archival titling. Used exclusively for page titles, record entry names (e.g., *Frankenstein*, *The Raven*), and section heads.
2. **Inter (Interface & Editorial Reading):** Neutral, high x-height sans-serif used for filters, descriptive summaries, long-form historical annotations, and primary form labels. Ensures optimal readability across variable screen conditions.
3. **IBM Plex Mono (MARC 21 & Telemetry):** Clean monospaced typeface for all machine-readable library fields (e.g., `001`, `020$a`, `245$b`, `650`), indicator bytes, memory offsets, and numerical metrics (decay rates, node IDs).

## Layout & Spacing
The layout model employs a structured, restrained fluid grid to mirror library index cabinets and analytical split-screen workstations.

- **Grid Architecture:** 12-column grid on desktop screens (`> 1024px`) with `2.5rem` outer canvas padding and `1.5rem` gutters. Tablet (`768px - 1023px`) contracts to 8 columns with `1.5rem` margins. Mobile (`< 767px`) operates on a 4-column framework with `1rem` margins.
- **Rhythm & Density:** Field filters and query parameters use compact vertical rhythms (`space-sm` to `space-md`), keeping the focal eye line on query outputs and graph nodes.
- **Two-Column Workstation:** On screens wider than 1280px, archive listings and terminal/graph visualization split into a coordinated 5:7 ratio or 6:6 layout to allow simultaneous inspection of source records alongside reconstructed MARC 21 graphs.

## Elevation & Depth
Depth is created through strict tonal tiering and architectural hairline boundaries rather than heavy drop shadows:

- **Level 0 (Canvas):** Pure `#0D0C0F`.
- **Level 1 (Card & Section Containers):** `#15131A` elevated surface. Outlined by an antique gold hairline border (`border: 1px solid rgba(212, 175, 55, 0.30)`).
- **Level 2 (Active Inspections / Flyouts):** `#1C1924` surface with a crisp gold outline (`border: 1px solid rgba(212, 175, 55, 0.60)`) and an ultra-diffused, ambient gold glow (`box-shadow: 0 8px 32px -4px rgba(212, 175, 55, 0.08)`).
- **Level 3 (Diagnostic & Terminal Views):** Recessed surfaces using `#080C0A` accompanied by a phosphor-tinted inner edge shadow (`inset 0 1px 3px rgba(0, 0, 0, 0.9), 0 0 12px rgba(57, 255, 20, 0.08)`), replicating physical CRT monitors and microfiche viewer windows.

## Shapes
The design language adopts a strict **Sharp (`0`)** corner geometry (`0px` border-radius across inputs, buttons, cards, tags, and progress tracks). 

The zero-radius discipline honors the sharp edges of archival index cards, cut bookbinding boards, microfiche film frames, and early computer terminals. It distinguishes the interface from standard rounded SaaS products, reinforcing a formal, clinical, and institutional presence.

## Components

### Buttons
- **Primary ("Summon" / "Execute"):** Background `#15131A`, text `#D4AF37`, border `1px solid #D4AF37`. On hover, background shifts to `#D4AF37` with `#0D0C0F` text and an antique gold drop glow (`box-shadow: 0 0 14px rgba(212, 175, 55, 0.35)`).
- **Terminal Action ("Resurrect"):** Background `#080C0A`, text `#39FF14`, border `1px solid rgba(57, 255, 20, 0.6)`. Hover triggers phosphor green backlight (`box-shadow: 0 0 16px rgba(57, 255, 20, 0.3)`).
- **Ghost / Auxiliary:** Transparent background, text `#A39E93`, border `1px solid rgba(212, 175, 55, 0.20)`. Hover shifts border to `rgba(212, 175, 55, 0.50)` and text to `#F3EFE6`.

### Inputs & Filters
- **Form Controls:** Background `#0D0C0F`, border `1px solid rgba(212, 175, 55, 0.30)`, typography `IBM Plex Sans` 14px in `#F3EFE6`. Placeholder text `#5A554C`.
- **Focus State:** Border shifts to crisp `1px solid #D4AF37` with an ambient glow (`box-shadow: 0 0 8px rgba(212, 175, 55, 0.2)`). No rounded corners.

### Chips & Provenance Badges
- **Subject / Topic Chips:** Monospace label encased in `0px` radius, background `rgba(212, 175, 55, 0.06)`, border `1px solid rgba(212, 175, 55, 0.25)`, text `#D4AF37`.
- **AI Provenance Badge:** Background `rgba(168, 85, 247, 0.12)`, border `1px solid #A855F7`, text `#C084FC`.
- **Decay Tag:** Background `rgba(239, 68, 68, 0.10)`, border `1px solid #EF4444`, text `#F87171`.

### Vitality & Telemetry Gauges
- **Progress Track:** Recessed bar (`height: 6px`), background `#101813`, border `1px solid rgba(57, 255, 20, 0.2)`.
- **Indicator Fill:** Solid `#39FF14` with a subtle phosphor bloom (`box-shadow: 0 0 8px rgba(57, 255, 20, 0.5)`).

### Record Cards
- Enclosed in `#15131A` with a 1px border `rgba(212, 175, 55, 0.30)`. Title rendered in `EB Garamond` (`#D4AF37`), metadata strings in `Inter` (`#A39E93`), and telemetry readouts in `IBM Plex Mono`.

### Knowledge Graph Legend & Inspector
- Dark card containers featuring dashed, dotted, and solid 1px swatch identifiers for ontological edge types (Shared Subject, Same Era, Semantic Similarity). Nodes styled with neon telemetry dots against archival obsidian backdrops.