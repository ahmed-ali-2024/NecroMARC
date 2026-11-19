# Design Document

## Overview

This design applies the Stitch "NecroMARC Archival Telemetry" identity (`docs/new_ui/necromarc_archival_telemetry/DESIGN.md` and the three `code.html` exports) to the Astro frontend in `frontend/`. The work is presentation only. It touches markup classes, `global.css`, component-local `<style is:global>` blocks, `theme.ts`, and two font dependencies.

The central design problem is that much of the DOM is built by code that Requirement 1 forbids editing. The archive cards are created by an inline `<script>` in `Archive.astro`. The resurrected card is built by `lib/card.ts`. The terminal lines are built by `lib/terminal.ts`. The Uploader and SemanticSearch result rows are built by inline scripts. All of these assign fixed class names such as `border border-gold/60 p-4 grid gap-2`. The design therefore uses two styling channels:

1. **Static markup** (Astro templates): the template classes are edited directly. Redundant color and border utilities are replaced with semantic classes (`btn`, `field`, `surface-1`, and so on).
2. **Generated DOM** (script and `lib/*.ts` output): the class names stay as they are. `global.css` restyles them with selectors scoped by id or by the existing generated class (`#record-list > li`, `.card-badge`, `.terminal-decay`).

### Research summary

| Finding | Source | Design consequence |
|---|---|---|
| Stitch loads Tailwind CDN, Google Fonts and Material Symbols from external hosts. | `docs/new_ui/*/code.html` head | Nothing is copied from the exports except values. Fonts come from `@fontsource`. Icons are inline SVG. |
| `@fontsource/inter` and `@fontsource/ibm-plex-sans` exist at 5.3.0, matching the pinned version of the three installed fontsource packages. | `npm view` | Pin both at `5.3.0` (exact, as in `package.json`). |
| Tailwind v4 emits utilities into `@layer utilities`. Unlayered CSS always beats layered CSS. | Tailwind v4 cascade-layer model | Component rules that must beat generated utility classes (for example `text-gold` on a hover fill) are written unlayered. |
| Tailwind v4 lets `@theme` clear a namespace with `--radius-*: initial`. | Tailwind v4 theme docs | Radius utilities are removed, so `rounded-*` cannot reintroduce rounded corners. |
| `block-size-[60vh]`, `inline-size-full`, `inline-size-4`, `block-size-4` and `max-block-size-64` are not Tailwind v4 utilities. The built CSS contains no rule for them. | `grep` of `frontend/dist/_astro/*.css` | The graph canvas currently gets no height from its class. See Decision D7. |
| `Header.astro` has no `aria-current`, and no page has a `<footer>`. | `grep` over `frontend/src` | Both are additive changes. See Decisions D5 and D6. |
| `Uploader.astro` only calls `preventDefault()` on `dragover`. It has no drag-state class or attribute. | `Uploader.astro` line 330 | Drag feedback uses `:hover` and `:focus-within`. See Decision D8. |

## Architecture

### File map and styling channels

```mermaid
flowchart LR
  subgraph Tokens
    GC[global.css @theme tokens]
    TM[lib/theme.ts THEME mirror]
    GC <-->|theme.test.ts equality| TM
  end
  subgraph Fonts
    FS[@fontsource packages]
    FS --> GC
  end
  subgraph Static markup
    BL[BaseLayout.astro]
    HD[Header.astro]
    PG[pages and components templates]
  end
  subgraph Generated DOM
    AR[Archive inline script]
    CD[lib/card.ts]
    TE[lib/terminal.ts]
    UP[Uploader and SemanticSearch scripts]
  end
  GC -->|semantic classes| BL
  GC -->|semantic classes| HD
  GC -->|semantic classes| PG
  GC -->|scoped selectors| AR
  GC -->|scoped selectors| CD
  GC -->|scoped selectors| TE
  GC -->|scoped selectors| UP
```

### Cascade strategy in `global.css`

`global.css` is organised in five blocks, in this order:

1. `@import 'tailwindcss'` and the `@fontsource` imports.
2. `@theme { ... }` tokens (colors, fonts, spacing, radius).
3. `@layer base { ... }`: element defaults (`html`, `body`, headings, links, `:focus-visible`, `:lang(ar)`, `.marc-text`, `.terminal`).
4. Unlayered **component rules**: surfaces, buttons, fields, chips, badges, gauges, header, grids. Each rule is scoped by a semantic class, an id, or an existing generated class.
5. Unlayered `@media (prefers-reduced-motion: reduce)` override.

Keeping `:lang(ar)` and the `.marc-text`/`.terminal` rules inside `@layer base` lets utilities such as `font-mono` still win. Within that layer `.marc-text, .terminal` stays after `:lang(ar)` because both have specificity (0,1,0) and the later rule wins. The terminal also carries `lang="und"`, so `:lang(ar)` does not match it.

All directional CSS uses logical properties (`margin-inline-*`, `padding-inline-*`, `inset-inline-*`, `border-inline-*`, `text-align: start`). Templates use `ms-*`, `me-*`, `ps-*`, `pe-*`, `start-*`, `end-*`.

### Design decisions

| ID | Decision | Rationale |
|---|---|---|
| D1 | Restyle generated DOM with CSS selectors. Do not edit inline script bodies or `lib/*.ts`. | Requirement 1.2 and 1.6. |
| D2 | Component rules are unlayered. | Hover fills must beat `text-gold` and similar utilities that generated DOM carries. |
| D3 | Keep token names `--color-ink`, `--color-parchment`, `--color-gold`, `--color-terminal-bg`, `--color-phosphor`, `--color-decay-red`, `--color-ai-violet`. Add `--color-card`, `--color-card-active`, `--color-muted`, `--color-ai-violet-text`, `--color-decay-text`. | `theme.test.ts` matches the old names. New names carry the Stitch text variants that pass contrast on every surface tier. |
| D4 | The header notice `#session-expired` is taken out of flow and anchored under the 80px bar. | Keeps the fixed header at exactly 80px when the notice shows. |
| D5 | `aria-current="page"` is computed in `Header.astro` frontmatter from `Astro.url.pathname`. | Build-time only. No inline script changes. Requirement 7.5 says "as it did before", but no `aria-current` exists today, so this is additive. |
| D6 | `BaseLayout.astro` gains one `<footer>` containing `app.name` and `app.tagline` through existing `data-i18n` keys. | Requirement 12.3 requires exactly one `footer`. No new i18n keys. |
| D7 | The dead `block-size-*` and `inline-size-*` classes are replaced with working Tailwind v4 logical utilities (`block-[60vh]`, `inline-full`, `size-4`, `max-block-64`). `#graph-canvas` also gets `min-block-size: 60vh` in `global.css`. | Without this the canvas has no height. This is a presentation fix inside an In_Scope_File. |
| D8 | Drop-zone feedback uses `:hover` and `:focus-within`. No script or attribute is added. | There is no drag-state class or attribute to hook. Adding one needs a script change, which Requirement 1 forbids. |
| D9 | Form-control resting borders use gold at 50%, not 30%. | Gold at 30% over `#0D0C0F` is 1.83:1. At 50% it is 3.09:1, which meets the 3:1 non-text rule. This deviates from the figure in Requirement 8.5 and is listed under Requirement deviations. |
| D10 | Fonts: EB Garamond for headings, Inter for body, IBM Plex Sans for labels and form text, IBM Plex Mono for MARC and telemetry, Amiri first for `:lang(ar)`. | Matches Stitch typography with Amiri taking Arabic. |

## Components and Interfaces

### Semantic classes (defined in `global.css`)

| Class | Purpose | Visual spec |
|---|---|---|
| `.surface-1` | Level 1 card or section | `background: var(--color-card)`, `border: 1px solid rgba(212,175,55,.30)`, radius 0 |
| `.surface-2` | Level 2 active surface, dialog | `background: var(--color-card-active)`, border gold 60%, `box-shadow: 0 8px 32px -4px rgba(212,175,55,.08)` |
| `.surface-3` | Level 3 recessed terminal and canvas | `background: var(--color-terminal-bg)`, `box-shadow: inset 0 1px 3px rgba(0,0,0,.9), 0 0 12px rgba(57,255,20,.08)` |
| `.btn` | Primary button | card background, gold text, 1px gold border. Hover and `:focus-visible`: gold fill, ink text, `box-shadow: 0 0 14px rgba(212,175,55,.35)` |
| `.btn-terminal` | Resurrect action | terminal background, phosphor text, border phosphor 60%. Hover: `box-shadow: 0 0 16px rgba(57,255,20,.3)` |
| `.btn-ghost` | Export and auxiliary | transparent, muted text, border gold 20%. Hover: border gold 50%, text parchment |
| `.field` | Input, textarea, select | ink background, 1px border gold 50%, Plex Sans 14px, parchment text, placeholder `#8A857A`. Focus: solid gold border, `box-shadow: 0 0 8px rgba(212,175,55,.2)` |
| `.chip` | Subject chip | mono, background gold 6%, border gold 25%, gold text |
| `.badge-ai` | AI provenance | background violet 12%, border `#A855F7`, text `--color-ai-violet-text` |
| `.tag-decay` | Decay tag | background red 10%, border `#EF4444`, text `--color-decay-text` |
| `.meter` and `.meter > i` | Vitality gauge | 6px track `#101813`, border phosphor 20%, fill phosphor with `box-shadow: 0 0 8px rgba(57,255,20,.5)` |

All of them set `border-radius: 0`. Every state that Stitch shows with color alone also carries a text label or shape (see Accessibility below).

### Per-file change plan

| File | Change |
|---|---|
| `global.css` | Add fonts, tokens, spacing, elevation, base typography, semantic classes, generated-DOM selectors, header and shell rules, reduced-motion block. No `http(s)://`. No physical properties. |
| `lib/theme.ts` | Mirror every color token (see Data Models). Same change as `global.css`. |
| `BaseLayout.astro` | `body` becomes a flex column. At 768px and up, `body` gets `padding-block-start: 5rem` for the fixed header. Add `<footer class="surface-1">` with `data-i18n="app.name"` and `data-i18n="app.tagline"`. `LoginModal` stays last in `body`. |
| `Header.astro` | Inner bar `min-block-size: 5rem` (exactly 5rem at 768px and up). Brand: 36px gold-bordered tile with inline SVG book icon (`aria-hidden="true"`) plus wordmark in EB Garamond gold. Nav: uppercase, `letter-spacing`, active item gold with 2px bottom border and glow via `a[aria-current="page"]`. Language toggle: bordered, radius 0. `#judge-login` and `#judge-logout`: `.btn`. Notice `#session-expired`: `position: absolute; inset-inline: 0; inset-block-start: 100%`, styled `.tag-decay`. Below 768px: header is in normal flow and wraps. All ids, `data-i18n`, `data-i18n-attr`, `hidden` and the script stay. |
| `LanguageToggle.astro` | Replace `border border-gold text-gold` with `.btn`. Keep `ms-2`, id and attributes. |
| `Archive.astro` template | `<section>` gets `max-w-7xl`. Form gets `.surface-1`. Inputs get `.field`. Buttons get `.btn`. `#semantic-slot` gets `.surface-1` with a violet left accent via `border-inline-start`. `#record-list` gets `grid-cols-1 md:grid-cols-2 xl:grid-cols-3` and `gap-gutter`. Pager buttons get `.btn`. |
| `Archive.astro` generated DOM | Styled by `#record-list > li` (Level 1, hover Level 2), `#record-list h2` (Garamond gold), `#record-list h2 + p` (Inter, muted), `#record-list [role="meter"]` (recessed 6px track) with `> span` fill (phosphor bloom), `#record-list .text-decay-red` (decay tag), `#record-list li ul > li` (chip). The inline script text is untouched. |
| `ResurrectedCard.astro` | `<section>` becomes Level 2 (`.surface-2`) and keeps `data-resurrected-card`, `aria-live` and `.resurrected-card`. Its `<style is:global>` block is rewritten with tokens: `.card-title` Garamond gold, `.card-badge` chip, `.card-ai` violet badge, `.card-meter-track` and `.card-meter-fill` gauge, `.card-decay-item` crimson tag in mono, `.card-export-link` ghost button, `.card-error` decay tag. |
| `DecayBreakdown.astro`, `ExportButtons.astro` | No markup change. Both only host `data-decay-breakdown` and `data-export-buttons`. Their look comes from the `ResurrectedCard` rules above. |
| `TerminalPanel.astro` | Keep `class="terminal marc-text ..."`, `dir="ltr"`, `lang="und"` and attribute order. Add `.surface-3 flex flex-col`. Change the `h2` from `sr-only` to a visible header strip (gold label, bottom hairline), keeping `data-i18n="terminal.title"`. The `ol` becomes the scroll region (`max-block-size: 70vh; overflow-y: auto`) so the strip stays visible. Line styles use phosphor text; `.terminal-decay` and `.terminal-ai` use `--color-decay-text` and `--color-ai-violet-text`. The reduced-motion block stays. |
| `chamber/index.astro` | Keep `grid gap-4 grid-cols-1 md:grid-cols-2 min-w-0` verbatim and append `xl:grid-cols-[5fr_7fr]`. `#chamber-resurrect` gets `.btn-terminal`. `#chamber-retry` and `#chamber-login` get `.btn`. `#chamber-error` gets `.tag-decay`. Keep `id="chamber-title"` with `dir="auto"`, both `hidden` attributes and every `href` built from `base`. |
| `Uploader.astro` template | `#uploader` gets `.surface-1`. `#up-drop` becomes `border border-dashed` gold with `:hover` and `:focus-within` rules (see D8). Buttons get `.btn`. `#up-search` gets `.field`. Status and error paragraphs use telemetry styles (mono, small). `aria-live`, `aria-busy` and ids stay. Rows built by the script (`#up-list > li`, `#up-outcome-list > li`) are styled by selector. |
| `LoginModal.astro` | Backdrop stays `bg-ink/80`. Dialog gets `.surface-2` and keeps `role="dialog"` and `aria-modal`. Inputs get `.field`. Submit and cancel get `.btn`. `#login-error` gets `.tag-decay`. Labels stay visible. |
| `SemanticSearch.astro` | Section `.surface-1` with violet accent. Textarea `.field`. Buttons `.btn`. `#ss-results > li` styled as Level 1 result cards. `#ss-error` gets `.tag-decay`. All `data-slot` and `aria-live` anchors stay. |
| `GraphCanvas.astro` | Replace `md:grid-cols-[1fr_18rem]` with `xl:grid-cols-[1fr_18rem]`. The `<aside>` gets `order-first xl:order-none` so the legend stacks above the canvas below 1280px. The list section uses `xl:col-span-2`. `#graph-canvas` gets `.surface-3`, a gold hairline border, `block-[60vh] inline-full`, and `min-block-size: 60vh` in CSS. The details section gets `.surface-1`. |
| `Legend.astro` | Section `.surface-1`. Edge swatches: 1px `stroke-width` with `stroke-dasharray` solid, `6 3`, `2 3`. Node dots stay as is (circle, rotated square, hexagon from the existing inline styles). Replace `inline-size-4 block-size-4` with `size-4`. |
| `MarcSources.astro` | Section `.surface-1`. Links keep `target`, `rel` and `data-source`. |
| `index.astro`, `summon/index.astro`, `graph/index.astro` | Page padding uses `px`-free logical tokens (`ps-4 pe-4` becomes `ps-margin-mobile pe-margin-mobile md:ps-margin md:pe-margin`). Titles use the Garamond display style. `graph/index.astro` form gets `.surface-1` and inputs `.field`. Imports are unchanged. |

### Header at the three widths

| Width | Behaviour |
|---|---|
| 768px and up | `position: fixed; inset-inline: 0; inset-block-start: 0; block-size: 5rem; background: rgba(13,12,15,.95); backdrop-filter: blur(16px); border-block-end: 1px solid #2A2530; z-index: 40`. `body` has `padding-block-start: 5rem`. |
| Below 768px | `position: static`. Brand, nav and controls wrap onto several rows. All four nav entries, the language toggle and the login button stay visible. |
| 320px | Same as below 768px. Nav links wrap. |

### Responsive grids

| Surface | below 768px | 768 to 1279px | 1280px and up |
|---|---|---|---|
| Archive `#record-list` | 1 column | 2 columns | 3 columns, `gap: var(--spacing-gutter)` |
| Chamber two-column container | 1 column | 2 equal columns | 5fr 7fr (terminal : card) |
| Summon container | 1 column | 2 columns | 2 columns |
| Graph aside and canvas | aside above canvas | aside above canvas | canvas then aside (18rem) |

Minimum target size below 768px: `button, nav a, #language-toggle` get `min-block-size: 2.75rem; min-inline-size: 2.75rem`.

### Icons

Stitch uses Material Symbols for `auto_stories` (brand tile), `person` (avatar), and chevrons or arrows in places. Only the brand tile icon is adopted. It is an inline `<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">` using `currentColor`. Directional arrows, if any are added, use `transform: scaleX(-1)` under `:dir(rtl)`. The Stitch avatar circle has no matching control and is omitted. The "Archival Catalog Telemetry" subtitle has no i18n key and is omitted (Requirement 2.10).

### Fonts

`global.css` imports, with exact weights referenced by the CSS:

| Package | Weights | Used by |
|---|---|---|
| `@fontsource/eb-garamond` | 400, 600, 400-italic (existing) | headings, card titles; italic by `.card-ai` and `.terminal-ai` |
| `@fontsource/amiri` | 400, 700 (existing) | `:lang(ar)` |
| `@fontsource/ibm-plex-mono` | 400 (existing) | `.marc-text`, `.terminal`, telemetry numbers, chips |
| `@fontsource/inter` (new, 5.3.0) | 400, 600 | body text, metadata, `title-md` |
| `@fontsource/ibm-plex-sans` (new, 5.3.0) | 400, 500, 600 | form controls (400), `label-md` (500), `label-sm` and nav (600) |

Font stacks:

```css
--font-serif: 'EB Garamond', 'Amiri', Garamond, Georgia, serif;
--font-sans: 'Inter', system-ui, sans-serif;
--font-label: 'IBM Plex Sans', 'Inter', system-ui, sans-serif;
--font-arabic: 'Amiri', 'EB Garamond', serif;
--font-mono: 'IBM Plex Mono', ui-monospace, monospace;
```

If either new package cannot be installed, the two `@import` lines are removed and `--font-sans` and `--font-label` collapse to `system-ui, sans-serif`. The build is unaffected because the stacks already end in system fonts.

## Data Models

### Design tokens (`@theme` in `global.css`)

| Token | Value | Notes |
|---|---|---|
| `--color-ink` | `#0d0c0f` | canvas, Level 0 |
| `--color-card` | `#15131a` | Level 1 |
| `--color-card-active` | `#1c1924` | Level 2 |
| `--color-terminal-bg` | `#080c0a` | Level 3 |
| `--color-gold` | `#d4af37` | |
| `--color-phosphor` | `#39ff14` | |
| `--color-ai-violet` | `#a855f7` | borders, fills, graphics |
| `--color-ai-violet-text` | `#c084fc` | text on any surface tier |
| `--color-decay-red` | `#ef4444` | borders, fills, graphics |
| `--color-decay-text` | `#f87171` | text on any surface tier |
| `--color-parchment` | `#f3efe6` | |
| `--color-muted` | `#a39e93` | metadata and ghost text |
| `--spacing-xs` / `-sm` / `-md` / `-lg` / `-xl` | `0.25` / `0.5` / `1` / `1.5` / `2.5` rem | |
| `--spacing-gutter` / `-margin` / `-margin-mobile` | `1.5rem` / `2.5rem` / `1rem` | |
| `--radius-*` | `initial`, then `--radius-none: 0` | removes rounded utilities |

Elevation values for Levels 0 to 3 are defined as custom properties (`--elev-1-border`, `--elev-2-border`, `--elev-2-glow`, `--elev-3-shadow`) with the values in Requirement 4.9.

### Theme mirror (`lib/theme.ts`)

```ts
export const THEME = {
  ink: '#0D0C0F', card: '#15131A', cardActive: '#1C1924', terminalBg: '#080C0A',
  parchment: '#F3EFE6', muted: '#A39E93', gold: '#D4AF37', phosphor: '#39FF14',
  decayRed: '#EF4444', decayText: '#F87171', aiViolet: '#A855F7', aiVioletText: '#C084FC',
} as const;
```

The seven keys that `theme.test.ts` reads keep their names. The new keys are not read by existing tests but are kept in sync by hand in the same change.

### Contrast ledger (Requirement 4.4 to 4.6)

Ratios use the WCAG 2.x formula, computed with the same function as `contrast.test.ts`.

**Existing test pairs with the Stitch palette** (all pass, no adjustment needed):

| Pair | Ratio | Minimum |
|---|---|---|
| parchment on ink | 17.00 | 4.5 |
| gold on ink | 9.28 | 4.5 and 3 |
| decay-red `#EF4444` on ink | 5.18 | 4.5 |
| ai-violet `#A855F7` on ink | 4.93 | 4.5 |
| phosphor on ink | 14.39 | 4.5 and 3 |
| phosphor on terminal-bg | 14.51 | 4.5 |
| decay-red on terminal-bg | 5.23 | 4.5 and 3 |
| ai-violet on terminal-bg | 4.97 | 4.5 and 3 |
| parchment on terminal-bg | 17.15 | 4.5 |

**Pairs the design adds** (Requirement 4.5 record):

| Token or use | Original | Surface | Ratio | Replacement | Replacement ratio |
|---|---|---|---|---|---|
| Violet as text | `#A855F7` | card-active `#1C1924` | 4.37 (fails 4.5) | `--color-ai-violet-text` `#C084FC` | 6.55 |
| Violet as text | `#A855F7` | card `#15131A` | 4.66 | `#C084FC` (used for consistency) | 6.97 |
| Decay red as text | `#EF4444` | card-active | 4.60 | `--color-decay-text` `#F87171` (margin) | 6.25 |
| Input placeholder | `#5A554C` | ink `#0D0C0F` | 2.64 (fails 4.5) | `#8A857A` | 5.31 (5.01 on card) |
| Input resting border | gold 30% (`#493D1B`) | ink | 1.83 (fails 3) | gold 50% (`#715E23`) | 3.09 |
| Muted text `#A39E93` | none | ink / card / active | 7.31 / 6.90 / 6.48 | not needed | |
| Gold text | none | card / active | 8.76 / 8.23 | not needed | |
| Phosphor 60% border | none | terminal-bg | 5.60 | not needed | |

Gold hairlines at 30% on cards (1.87:1) are decorative separators. The card content is identified by its surface tier and its text, so they are not held to 3:1. Muted `#A39E93` is only used on ink, card, card-active and terminal backgrounds, all at 6.48 or above.

### i18n and DOM contracts

No key is added, removed or renamed in `en.json` or `ar.json`. The footer reuses `app.name` and `app.tagline`. Every `id`, `data-i18n`, `data-i18n-attr`, `data-slot`, `role`, `aria-*` and `hidden` attribute in the In_Scope_Files is preserved. Wrappers, where needed, go around existing elements.

## Error Handling

| Condition | Handling |
|---|---|
| `@fontsource/inter` or `@fontsource/ibm-plex-sans` cannot install | Remove its `@import` lines and its `package.json` and lockfile entries. Set the font stack variables to `system-ui, sans-serif`. The build and tests are unaffected (Requirement 3.5). |
| IBM Plex Mono fails to load | `.marc-text` and `.terminal` fall back to `ui-monospace, monospace`, keeping `direction: ltr` and `text-align: left` (Requirement 6.6). |
| Archive returns zero records | Existing script writes `archive.empty` to `#status`. The `<ul>` is empty and the form stays visible and enabled. No CSS hides the form. |
| Resurrected record has no summary or topics | `card.ts` omits those elements. The CSS must not add pseudo-element placeholders (`::before`/`::after` content) to `.card-summary` or `.card-subjects`. |
| DecayBreakdown has no factors | `.card-decay-list` renders empty. The CSS gives no minimum height to an empty list. |
| Semantic search fails or is empty | The existing `aria-live` region gets a Level 1 card style through `#ss-results` and the status element. The input value is left alone because no script is touched. |
| Login error | `#login-error` keeps `role="alert"` and gets `.tag-decay`. Username and password handling stay in the existing script. |
| Contrast fails after a token change | Fix the token, not the test. Update `theme.ts` in the same change and record the new ratio in the ledger above. |
| Verification command fails | Edit only In_Scope_Files, then rerun until exit code 0 (Requirement 13.8). |

## Testing Strategy

Property-based testing does not apply, so this design has no Correctness Properties section. The feature is CSS, markup, design tokens and dependency changes. It has no pure function with a meaningful "for all inputs" statement. The existing property tests (`i18n.property.test.ts`, `graph.property.test.ts`, `upload.property.test.ts`) cover unchanged logic and must keep passing. The token contrast and mirror checks are finite and are covered by example tests. Verification uses the existing example-based suites and a small set of repeatable shell checks.

**Constraint on new tests.** Requirement 1.1 limits modified files to the In_Scope_Files, `theme.ts` and the font dependency entries. Adding or editing a test file would break that rule. The existing tests therefore stay byte-identical, and the extra checks below run as shell commands and are not committed.

### Existing suites (must pass unchanged, 124 of 124)

| Suite | What it guards |
|---|---|
| `theme.test.ts` | `--color-<name>: <hex>;` for the seven names, equal to `THEME`. No `http(s)://` in `global.css`. Amiri import present. |
| `contrast.test.ts` | Text pairs at 4.5 and UI pairs at 3 with the new palette. |
| `i18n.property.test.ts` | No physical utilities under `src/`. Key parity of `en.json` and `ar.json`. |
| `_layout.test.ts` | `grid-cols-1 md:grid-cols-2`, `min-w-0`, `BASE_URL` links, `hidden` ids, `terminal marc-text` plus `dir="ltr"` order, `lang="und"`, `dir="auto"` on `chamber-title`. |
| `components.dom.test.ts`, `chamber.dom.test.ts` | Ids, `data-slot`, `aria-*`, `hidden` states, focus handling, custom events. |
| `_about.test.ts`, `bundle.test.ts` | About page structure and bundle scan rules. |

### Shell checks (run before accepting)

| Requirement | Check |
|---|---|
| 1.1, 1.2 | `git diff --name-only` lists only In_Scope_Files, `theme.ts`, `package.json`, `package-lock.json`. `git diff --stat -- frontend/src/lib frontend/src/i18n` shows only `theme.ts`. |
| 1.2 (inline scripts) | `git diff` of each `.astro` file, filtered to lines between `<script>` and `</script>`, is empty. |
| 2.1 | Extract `id=`, `data-i18n=`, `data-i18n-attr=`, `data-slot=`, `role=`, `aria-*=`, `hidden` from each In_Scope_File at the base commit and at HEAD. The base set must be a subset of the HEAD set. |
| 3.1, 3.2 | `grep -rE 'https?://\|fonts\.g\|cdn\.tailwindcss\|material-symbols' frontend/src frontend/dist` returns no match, except pre-existing `<a href>` values in `MarcSources.astro` (data from `lib/marcSources.ts`). |
| 3.9 | Open each page in `astro preview` and confirm the network list has the site origin only. |
| 5.1 | `i18n.property.test.ts` plus `grep -nE '(margin\|padding)-(left\|right)\|border-(left\|right)\|text-align: *(left\|right)\|(^\|[ {;])(left\|right):' frontend/src/styles/global.css`. The `.marc-text` left alignment under RTL uses `text-align: start` on an LTR element, so no `left` keyword is needed. |
| 7, 8, 9, 10, 11, 12 | Manual pass with the preview build at 320px, 375px, 768px and 1280px, in English and Arabic: header height, no horizontal scroll, 44px targets, focus outline, grid column counts, reduced-motion (emulated), RTL mirroring. A grayscale pass checks Requirement 12.6. |
| 12.3 | In the built HTML of each page, count `<header`, `<main`, `<footer` (one each), at least one `<nav`, and one `<h1`. |
| 13.3 | `PUBLIC_BASE_PATH=/necromarc PUBLIC_API_URL=https://3aai.in/necromarc/api npm run check:bundle` |
| 13.7 | `git check-ignore .kiro/specs/stitch-ui-redesign/design.md` returns no match. |

### Verification commands

```
npm test
npm run check:i18n
PUBLIC_BASE_PATH=/necromarc PUBLIC_API_URL=https://3aai.in/necromarc/api npm run check:bundle
```

## Requirement deviations and open findings

These are places where the approved requirements and the current code disagree or cannot both be met. The design applies the default stated beside each. They should be confirmed or the requirement amended.

| # | Finding | Design default |
|---|---|---|
| 1 | Requirement 8.5 asks for form-control borders at gold 30%. That gives 1.83:1 against the canvas, below the 3:1 non-text minimum. | Resting form borders at gold 50% (3.09:1). Cards keep 30%. Amend 8.5 to 50% for form controls. |
| 2 | Requirement 7.5 says `aria-current` is set "as before", but `Header.astro` never set it. | Add it at build time (D5). |
| 3 | Requirement 12.3 needs one `footer`. No page has one. | Add one to `BaseLayout.astro` (D6). |
| 4 | Requirement 10.2 and 10.3 refer to an "existing drag-state class or attribute". None exists. | Use `:hover` and `:focus-within` (D8). Native drag-over feedback is not styled. Meeting it exactly needs a script change. |
| 5 | Requirement 9.8 wants the numeric value in monospace. `card.ts` emits one text node per row (`"{name}: {points}"`). | Whole `.card-decay-item` row is monospace. Splitting the number needs a `card.ts` change. |
| 6 | Requirement 1.1 forbids touching test files, so new tests cannot be committed with the redesign. | Shell checks and existing suites (see Testing Strategy). |
| 7 | Requirement 11.5 says to keep the canvas minimum height "unchanged". The class that should provide it generates no CSS. | Set a real height (D7). |
| 8 | Requirement 8.3 lists an Archive AI-generated marker. Archive cards show none; only the resurrected card and terminal have one. | Style `.card-ai` and `.terminal-ai`. Add nothing to Archive cards. |
