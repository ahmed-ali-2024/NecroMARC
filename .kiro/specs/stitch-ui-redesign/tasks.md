# Implementation Plan: Stitch UI Redesign

## Overview

This plan applies the Stitch "NecroMARC Archival Telemetry" identity to the Astro frontend in `frontend/`. Implementation languages are CSS (Tailwind v4), Astro templates and one TypeScript constant file (`lib/theme.ts`). The design has no Correctness Properties section, so the plan has no property test tasks. Existing suites (124 tests) are the regression gate, and no test file may be edited (Requirement 1.1).

Work order: dependencies and tokens first, then shared CSS, then per-file markup, then verification. All edits stay inside the In_Scope_Files. Inline `<script>` bodies, `frontend/src/lib/*.ts` (except `theme.ts`), `frontend/src/i18n/*`, and the backend are never touched. Every `id`, `data-i18n`, `data-i18n-attr`, `data-slot`, `role`, `aria-*` and `hidden` attribute is kept. Use only logical utilities (`ms-`, `me-`, `ps-`, `pe-`, `start-`, `end-`, `text-start`, `text-end`) and logical CSS properties.

## Tasks

- [x] 1. Foundation: fonts, tokens, shared CSS
  - [x] 1.1 Add self-hosted font dependencies
    - Add `@fontsource/inter` and `@fontsource/ibm-plex-sans` at exact version `5.3.0` to `frontend/package.json` and update `frontend/package-lock.json` (run `npm install` in `frontend/`)
    - If either package cannot be installed, omit it and its imports, and set `--font-sans` and `--font-label` to `system-ui, sans-serif` (Requirement 3.5)
    - Do not add any forbidden ML dependency
    - _Requirements: 3.3, 3.4, 3.5, 13.6_

  - [x] 1.2 Rewrite `global.css` imports, `@theme` tokens and `@layer base`
    - Import only the weights that are referenced: EB Garamond 400/600/400-italic, Amiri 400/700, IBM Plex Mono 400, Inter 400/600, IBM Plex Sans 400/500/600
    - Declare colors (`--color-ink #0d0c0f`, `--color-card`, `--color-card-active`, `--color-terminal-bg`, `--color-gold`, `--color-phosphor`, `--color-ai-violet`, `--color-ai-violet-text`, `--color-decay-red`, `--color-decay-text`, `--color-parchment`, `--color-muted`) with exactly one `--color-<name>: <hex>;` per name
    - Declare font stacks, the spacing scale (`xs`..`xl`, `gutter`, `margin`, `margin-mobile`), `--radius-*: initial` with `--radius-none: 0`, and elevation custom properties for Levels 0 to 3
    - In `@layer base`: body typography and canvas background, heading fonts, `:lang(ar)` with Amiri first, `.marc-text, .terminal` (IBM Plex Mono then `monospace`, `direction: ltr`, `unicode-bidi: isolate`, `text-align: start`), gold `:focus-visible` outline of at least 2px
    - Use only logical properties, and include no `http://` or `https://` text
    - _Requirements: 3.3, 3.4, 3.7, 3.8, 4.1, 4.2, 4.7, 4.8, 4.9, 5.4, 6.1, 6.3, 6.5, 6.6, 7.1, 7.11_

  - [x] 1.3 Mirror colors in `frontend/src/lib/theme.ts`
    - Update `THEME` to the Stitch values and add `card`, `cardActive`, `muted`, `decayText`, `aiVioletText`, keeping the seven existing keys that `theme.test.ts` reads
    - Values must equal those in `global.css`
    - _Requirements: 4.1, 4.3, 4.4, 4.5_

  - [x] 1.4 Add semantic component classes to `global.css` (unlayered)
    - Add `.surface-1`, `.surface-2`, `.surface-3`, `.btn`, `.btn-terminal`, `.btn-ghost`, `.field`, `.chip`, `.badge-ai`, `.tag-decay`, `.meter` per the design's class table, all with `border-radius: 0`
    - `.field` rests at gold 50% border, focus gives solid gold border and glow; placeholder color `#8A857A`
    - `.btn` fills gold on hover and `:focus-visible`; `.btn-terminal` glows phosphor on hover; `.btn-ghost` goes gold 50% border and parchment text on hover
    - Add the `@media (prefers-reduced-motion: reduce)` block setting transitions to 0ms
    - Add 44px minimum target rules for `button`, `nav a`, `#language-toggle` below 768px
    - _Requirements: 4.7, 4.9, 7.8, 7.11, 7.12, 8.1, 8.3, 8.4, 8.5, 8.6, 9.10, 9.11, 9.12, 9.13, 10.5, 12.2, 12.6_

  - [x] 1.5 Add generated-DOM, header and layout selectors to `global.css`
    - Style script-generated DOM by existing selectors: `#record-list > li` (Level 1, hover Level 2), `#record-list h2`, `#record-list h2 + p`, `#record-list [role="meter"]` with a 6px recessed track and phosphor bloom fill, `#record-list .text-decay-red` as a decay tag, `#record-list li ul > li` as chip, `#up-list > li`, `#up-outcome-list > li`, `#ss-results > li`
    - Add `#graph-canvas { min-block-size: 60vh }`
    - Add header rules: fixed 5rem bar at 768px and up with 95% ink background, backdrop blur and 1px bottom border; static and wrapping below 768px; `a[aria-current="page"]` gold with 2px bottom border and glow; `#session-expired` anchored with `inset-inline: 0; inset-block-start: 100%`
    - Add `body` flex-column layout and `padding-block-start: 5rem` at 768px and up
    - Add `.terminal` Level 3 styles, phosphor text, `.terminal-decay` and `.terminal-ai` colors, and the scroll region for the terminal list
    - Add `.drop-zone`-style rules for `#up-drop` using dashed gold border, with `:hover` and `:focus-within` solid border and Level 2 glow
    - Do not add `::before` or `::after` placeholder content to `.card-summary` or `.card-subjects`
    - _Requirements: 6.1, 6.4, 7.2, 7.5, 7.9, 7.10, 8.1, 8.2, 8.3, 8.4, 8.10, 9.4, 9.5, 9.7, 9.9, 10.1, 10.2, 10.3, 10.4, 11.1, 11.5, 12.1_

- [x] 2. Checkpoint - Ensure all tests pass
  - Run `npm test` in `frontend/`; `theme.test.ts` and `contrast.test.ts` must pass. Ensure all tests pass, ask the user if questions arise.

- [x] 3. Global shell and header
  - [x] 3.1 Update `BaseLayout.astro`
    - Apply canvas background, parchment text and body typography; make `body` a flex column
    - Add one `<footer class="surface-1">` with `data-i18n="app.name"` and `data-i18n="app.tagline"` (no new keys); keep `LoginModal` last in `body`
    - Keep `lang` and `dir` handling and the initial i18n script unchanged
    - _Requirements: 7.1, 7.10, 12.3, 12.4, 2.9_

  - [x] 3.2 Restyle `Header.astro`
    - Brand tile (36px gold-bordered square with inline SVG, `aria-hidden="true"`, `focusable="false"`) and EB Garamond gold wordmark
    - Uppercase letter-spaced nav; compute `aria-current="page"` in frontmatter from `Astro.url.pathname`
    - `#judge-login` and `#judge-logout` use `.btn`; `#session-expired` uses `.tag-decay`
    - Keep every id, `data-i18n`, `data-i18n-attr`, `hidden` and the script untouched; use logical utilities only
    - Omit the Stitch subtitle and avatar (no i18n key, no matching control)
    - _Requirements: 2.10, 3.6, 5.2, 5.3, 7.2, 7.3, 7.4, 7.5, 7.7, 7.8, 7.9_

  - [x] 3.3 Restyle `LanguageToggle.astro`
    - Replace `border border-gold text-gold` with `.btn`; keep `ms-2`, the id and all attributes
    - _Requirements: 7.6_

- [x] 4. Home and Archive
  - [x] 4.1 Restyle the `Archive.astro` template
    - Section `max-w-7xl`; form `.surface-1`; inputs `.field`; buttons and pager buttons `.btn`; `#semantic-slot` `.surface-1` with `border-inline-start` violet accent
    - `#record-list` gets `grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-gutter`
    - Do not edit the inline script; keep ids, order of pagination, filter, sort and empty-state elements
    - _Requirements: 8.1, 8.5, 8.6, 8.7, 8.8, 8.9, 8.10, 8.11, 8.12, 1.2_

- [x] 5. Resurrection Chamber
  - [x] 5.1 Rewrite the `ResurrectedCard.astro` markup and `<style is:global>`
    - Section becomes `.surface-2`, keeping `data-resurrected-card`, `aria-live` and `.resurrected-card`
    - Style `.card-title`, `.card-badge`, `.card-ai`, `.card-meter-track`, `.card-meter-fill`, `.card-decay-item` (monospace crimson tag), `.card-export-link` (ghost button), `.card-error` (decay tag) using tokens
    - Give empty `.card-decay-list` no minimum height; keep `dir="auto"` on user text elements
    - `DecayBreakdown.astro` and `ExportButtons.astro` need no markup change
    - _Requirements: 9.6, 9.7, 9.8, 9.9, 9.10, 9.11, 5.5_

  - [x] 5.2 Restyle `TerminalPanel.astro`
    - Keep `class="terminal marc-text ..."`, `dir="ltr"`, `lang="und"` and attribute order; add `.surface-3 flex flex-col`
    - Make the `h2` a visible header strip (keep `data-i18n="terminal.title"`); make the `ol` the vertical scroll region
    - _Requirements: 6.2, 6.4, 9.4, 9.5_

  - [x] 5.3 Restyle `chamber/index.astro`
    - Keep `grid gap-4 grid-cols-1 md:grid-cols-2 min-w-0` verbatim and append `xl:grid-cols-[5fr_7fr]`
    - `#chamber-resurrect` `.btn-terminal`; `#chamber-retry` and `#chamber-login` `.btn`; `#chamber-error` `.tag-decay`
    - Keep `id="chamber-title"` with `dir="auto"`, both `hidden` attributes, and the `${base}/` and `${base}/chamber/?id=` link construction
    - _Requirements: 9.1, 9.2, 9.3, 9.12, 9.14, 9.15, 5.6, 2.6_

- [x] 6. Summon page, Uploader and Login modal
  - [x] 6.1 Restyle `Uploader.astro` template and `summon/index.astro`
    - `#uploader` `.surface-1`; `#up-drop` dashed gold border; buttons `.btn`; `#up-search` `.field`; status and error paragraphs in mono telemetry style
    - Keep `aria-live`, `aria-busy`, ids and script untouched
    - In `summon/index.astro` use Garamond display title and shell padding tokens; imports unchanged
    - _Requirements: 10.1, 10.4, 10.5, 10.11, 8.13_

  - [x] 6.2 Restyle `LoginModal.astro`
    - Dialog `.surface-2` with zero radius over `bg-ink/80` backdrop; inputs `.field` with visible labels; submit and cancel `.btn`; `#login-error` `.tag-decay`
    - Keep `role="dialog"`, `aria-modal`, `role="alert"`, ids and the focus-trap script
    - _Requirements: 10.6, 10.7, 10.8, 10.9, 10.10_

- [x] 7. Graph page
  - [x] 7.1 Restyle `SemanticSearch.astro`
    - Section `.surface-1` with violet accent; textarea `.field`; buttons `.btn`; `#ss-error` `.tag-decay`
    - Keep every id, `data-slot` and `aria-live` region
    - _Requirements: 11.1, 11.9_

  - [x] 7.2 Restyle `GraphCanvas.astro`
    - Replace `md:grid-cols-[1fr_18rem]` with `xl:grid-cols-[1fr_18rem]`; aside gets `order-first xl:order-none`; list section `xl:col-span-2`
    - `#graph-canvas` gets `.surface-3`, gold hairline border, `block-[60vh] inline-full`; details section `.surface-1`
    - Keep the container id and do not touch cytoscape setup
    - _Requirements: 11.5, 11.6, 11.7, 11.8_

  - [x] 7.3 Restyle `Legend.astro`
    - Section `.surface-1`; edge swatches 1px with solid, `6 3` dashed and `2 3` dotted strokes; replace `inline-size-4 block-size-4` with `size-4`
    - Keep every `data-i18n` key and the `graph:filters` and `graph:clear` dispatching script
    - _Requirements: 11.2, 11.3, 11.4_

  - [x] 7.4 Restyle `MarcSources.astro` and `graph/index.astro`
    - `MarcSources`: section `.surface-1`, keep `target`, `rel`, `data-source`
    - `graph/index.astro`: form `.surface-1`, inputs `.field`, shell padding tokens; imports unchanged
    - _Requirements: 11.1, 8.13_

- [x] 8. Home page
  - [x] 8.1 Restyle `index.astro`
    - Use shell padding tokens (`ps-margin-mobile pe-margin-mobile md:ps-margin md:pe-margin`) and Garamond title; keep imports and the single `h1`
    - _Requirements: 8.13, 12.3_

- [x] 9. Verification
  - [x] 9.1 Run the verification commands and fix failures
    - In `frontend/` run `npm test` (124 passed), `npm run check:i18n` (0 missing, 0 unused), and `PUBLIC_BASE_PATH=/necromarc PUBLIC_API_URL=https://3aai.in/necromarc/api npm run check:bundle`
    - On failure edit only the In_Scope_Files, then rerun until all exit 0
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.8_

  - [x] 9.2 Run the static scope checks
    - `git diff --name-only` lists only In_Scope_Files, `theme.ts`, `package.json`, `package-lock.json`; `git diff --stat -- frontend/src/lib frontend/src/i18n` shows only `theme.ts`
    - Grep `frontend/src` and `frontend/dist` for `https?://`, `fonts.g`, `cdn.tailwindcss`, `material-symbols` (only pre-existing `<a href>` values allowed)
    - Grep `global.css` and `frontend/src` for physical utilities and properties
    - Confirm each built page has one `<header`, one `<main`, one `<footer`, at least one `<nav`, one `<h1`
    - Confirm `git check-ignore .kiro/specs/stitch-ui-redesign/design.md` returns no match
    - _Requirements: 1.1, 1.2, 3.1, 3.2, 5.1, 12.3, 13.5, 13.7_

- [x] 10. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- No property-based tests: the design has no Correctness Properties section. No new test files are added because Requirement 1.1 forbids modifying files outside the In_Scope_Files.
- Browser checks (320/375/768/1280px, RTL, reduced motion, grayscale) from the design's testing strategy are manual and are not tasks here.
- The deviations listed in the design (form borders at 50%, additive `aria-current` and footer, no drag-state class) are applied as the design states.
- Tasks in the same wave touch different files; `global.css` tasks are placed in separate waves.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2"] },
    { "id": 2, "tasks": ["1.3", "1.4"] },
    { "id": 3, "tasks": ["1.5"] },
    { "id": 4, "tasks": ["3.1", "3.2", "3.3", "4.1", "5.1", "5.2", "5.3", "6.1", "6.2", "7.1", "7.2", "7.3", "7.4", "8.1"] },
    { "id": 5, "tasks": ["9.1", "9.2"] }
  ]
}
```
