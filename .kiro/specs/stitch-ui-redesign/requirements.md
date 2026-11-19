# Requirements Document

## Introduction

This feature applies the Google Stitch visual identity ("NecroMARC Archival Telemetry", sources in `docs/new_ui/`) to the NecroMARC Astro frontend. The change is presentation only: layout, cards, borders, gradients, spacing, typography and color. Application logic, API calls, routes, `frontend/src/lib/*.ts` behavior, and backend code stay unchanged.

The Stitch design defines: Dark Archival Luxury with Retro-Phosphor Telemetry; zero-radius corners; gold hairline borders at 30% opacity; tonal surface tiers (canvas, card, active, terminal); a fixed top header with gold active-tab underline; a 5:7 or 6:6 two-column workstation on wide screens; EB Garamond for titles, Inter for interface text, IBM Plex Mono for MARC and telemetry; phosphor vitality bars; gold topic chips, violet AI provenance badges, and crimson decay tags.

Constraints inherited from the project and from existing automated tests:

- The Stitch HTML exports load Tailwind CDN, Google Fonts and Material Symbols from external hosts. None of these may reach the frontend.
- Existing DOM hooks, i18n attributes, ARIA attributes and custom events are contracts used by inline scripts and by `components.dom.test.ts`, `chamber.dom.test.ts` and `_layout.test.ts`.
- Only logical CSS properties are allowed under `frontend/src/` (`i18n.property.test.ts`).
- `global.css` color tokens are mirrored in `src/lib/theme.ts` and checked by `theme.test.ts` and `contrast.test.ts`.

### Reference observations from the Stitch files

- The three `code.html` files share one header: fixed, 80px high, `#0D0C0F` at 95% opacity with backdrop blur, bottom border `#2A2530`, brand block with gold-bordered icon tile, uppercase nav (Archive, Summon, Graph, About), language switch, and a bordered gold "Judge Login" button.
- The Stitch design colors differ from the current tokens (for example, ink `#12100E` vs canvas `#0D0C0F`, phosphor `#4DFF88` vs `#39FF14`, violet `#C9A6FF` vs `#A855F7`, decay red `#FF7A7A` vs `#EF4444`). Each change needs a contrast check.
- Stitch uses physical utilities (`left-0`, `right-0`, `ml-*`, `pl-*`, `text-left`) in its markup. These must be translated to logical equivalents when porting.

## Glossary

- **Frontend**: The Astro static site in `frontend/`.
- **Stitch_Design**: The design sources in `docs/new_ui/` (`DESIGN.md`, three `code.html` files, two `screen.png` files).
- **Design_Tokens**: The color, font, spacing and radius values declared in the `@theme` block of `frontend/src/styles/global.css`.
- **Theme_Mirror**: The `THEME` constant in `frontend/src/lib/theme.ts` that duplicates the color Design_Tokens.
- **In_Scope_Files**: `global.css`, `BaseLayout.astro`, the components `Header`, `Archive`, `TerminalPanel`, `ResurrectedCard`, `DecayBreakdown`, `ExportButtons`, `LoginModal`, `Uploader`, `SemanticSearch`, `GraphCanvas`, `Legend`, and the pages `index.astro`, `chamber/index.astro`, `graph/index.astro`, `summon/index.astro`.
- **DOM_Hooks**: Element `id` attributes, `data-i18n`, `data-i18n-attr`, `data-slot`, `role`, `aria-*` attributes (including `role="meter"`, `aria-valuenow`, `aria-live`, `aria-busy`), `hidden` attribute initial states, and class names or selectors that inline scripts query.
- **Custom_Events**: `login:open`, `auth:changed`, `auth:expired`, `i18n:changed`, `graph:filters`, `graph:clear`.
- **Logic_Files**: `frontend/src/lib/*.ts` (excluding tests), `frontend/src/i18n/*.ts`, inline `<script>` bodies in `.astro` files, and all backend code.
- **Physical_Utilities**: Tailwind classes or CSS properties tied to left or right: `ml-`, `mr-`, `pl-`, `pr-`, `left-`, `right-`, `text-left`, `text-right`.
- **Logical_Utilities**: `ms-`, `me-`, `ps-`, `pe-`, `start-`, `end-`, `text-start`, `text-end`, and CSS logical properties.
- **Marc_Surface**: Any element with class `marc-text` or `terminal`.
- **Test_Suite**: The command `npm test` in `frontend/` (124 tests).
- **Verification_Commands**: `npm test`, `npm run check:i18n`, and `PUBLIC_BASE_PATH=/necromarc PUBLIC_API_URL=https://3aai.in/necromarc/api npm run check:bundle`.

## Requirements

### Requirement 1: Restrict the change to presentation in the listed files

**User Story:** As a maintainer, I want the redesign limited to markup, classes and styles in the listed files, so that application behavior stays identical.

#### Acceptance Criteria

1. THE Frontend SHALL limit the set of files modified by the redesign to the In_Scope_Files, `frontend/src/lib/theme.ts`, and the font dependency entries in `frontend/package.json` and `frontend/package-lock.json` needed by Requirement 3, such that a file-level diff against the pre-redesign commit lists zero modified files outside that set.
2. THE Frontend SHALL keep the content of every Logic_File byte-identical to its pre-redesign content, except for `frontend/src/lib/theme.ts` as allowed by Requirement 4, such that a checksum comparison of each Logic_File other than `theme.ts` against the pre-redesign commit reports zero differences.
3. THE Frontend SHALL keep every route path, every `href` target built from `import.meta.env.BASE_URL`, and every API endpoint string character-for-character identical to its pre-redesign value, such that a text search of the In_Scope_Files for those strings returns the same matches before and after the redesign.
4. THE Frontend SHALL keep the set of pages and their URLs identical to the pre-redesign set, with zero pages added, removed, or renamed.
5. WHEN a redesigned page is rendered, THE Frontend SHALL expose each of the user-visible actions navigate, switch language, log in, upload, resurrect, search, filter graph, and export through the same control type (link, button, or form field) and the same event handler binding as before the redesign, so that executing each action produces the same outcome as before the redesign.
6. IF a change to an In_Scope_File alters an event handler binding, a form field name, a data attribute read by a Logic_File, or an element identifier read by a Logic_File, THEN THE Frontend SHALL treat the change as a violation of this requirement and the change SHALL be reverted before the redesign is accepted.

### Requirement 2: Preserve DOM hooks and custom events

**User Story:** As a developer, I want every DOM hook and event contract preserved, so that inline scripts and DOM tests keep working.

#### Acceptance Criteria

1. WHEN the redesign is complete, THE Frontend SHALL contain every DOM_Hooks attribute name and value that was present in the In_Scope_Files before the redesign, with zero attributes removed, renamed, or changed in value.
2. WHEN the redesign is complete, THE Frontend SHALL keep every `data-slot` injection target as a descendant of the same logical component that contained it before the redesign.
3. WHEN the redesign is complete, THE Frontend SHALL contain every `data-i18n` and `data-i18n-attr` attribute on the same element with its original key and, for `data-i18n-attr`, its original attribute mapping.
4. WHEN the redesign is complete, THE Frontend SHALL keep `role="meter"`, `aria-valuenow`, `aria-valuemin`, `aria-valuemax`, `aria-live` and `aria-busy` on every element that had them before the redesign, with the same initial values.
5. WHEN the redesign is complete, THE Frontend SHALL contain every dispatch site and listener site for each of the Custom_Events, with the event name and `detail` payload shape (property names and value types) unchanged.
6. WHEN the page first loads, THE Frontend SHALL render `chamber-resurrect` and `chamber-guest`, and every other element that had `hidden` before the redesign, with the `hidden` attribute set.
7. WHEN a class name is used as a selector by an inline script or test, THE Frontend SHALL keep that class name on the same element.
8. IF a redesign needs a wrapper element, THEN THE Frontend SHALL add the wrapper around the existing element, keep the existing element's attributes and id unchanged, and keep the existing element's index among its script-queried siblings unchanged.
9. THE Frontend SHALL leave all keys and values in `en.json` and `ar.json` unchanged, with zero keys added, removed, or renamed.
10. WHERE the Stitch_Design contains text that has no existing key in `en.json` and `ar.json` (for example the "Archival Catalog Telemetry" subtitle), THE Frontend SHALL omit that text and SHALL NOT add a hardcoded string in its place.

### Requirement 3: Self-hosted fonts and icons

**User Story:** As a deployer, I want all fonts and icons served from the site itself, so that the build has no third-party requests.

#### Acceptance Criteria

1. THE Frontend SHALL contain zero occurrences of the strings `http://` or `https://` in `global.css`, `BaseLayout.astro`, and the markup of every other In_Scope_File, except in `href` attributes of `<a>` elements that existed before the redesign.
2. THE Frontend SHALL contain zero references to the Tailwind CDN script, `fonts.googleapis.com`, `fonts.gstatic.com`, or Material Symbols from the Stitch_Design in any In_Scope_File and in the built static output.
3. THE Frontend SHALL load EB Garamond, Amiri and IBM Plex Mono from the existing `@fontsource` packages.
4. WHERE Inter and IBM Plex Sans are adopted for interface text and labels, THE Frontend SHALL load them from the self-hosted `@fontsource/inter` and `@fontsource/ibm-plex-sans` packages imported in `global.css`, and SHALL import only the weights that `global.css` or In_Scope_File markup references, so that no unused weight file is imported.
5. IF the `@fontsource/inter` or `@fontsource/ibm-plex-sans` package cannot be installed, THEN THE Frontend SHALL render interface text with a local `system-ui` sans-serif font stack, SHALL contain no reference to the missing package, and SHALL still build without error.
6. WHEN an icon is needed that the Stitch_Design draws with Material Symbols, THE Frontend SHALL render it as an inline SVG or CSS shape carrying `aria-hidden="true"`, and SHALL NOT load any icon font file.
7. THE Frontend SHALL apply Amiri as the first font family in the `font-family` declaration for elements matching `:lang(ar)`.
8. WHEN the `theme.test.ts` suite runs, THE Frontend SHALL pass all of its tests, including the check that `global.css` contains no `http://` or `https://` text.
9. WHEN a built page is loaded in a browser, THE Frontend SHALL issue zero network requests to any origin other than the site's own origin for fonts, stylesheets, scripts, and icons.

### Requirement 4: Design tokens and theme mirror

**User Story:** As a designer, I want the Stitch palette expressed as Design_Tokens, so that components share one visual identity.

#### Acceptance Criteria

1. THE Design_Tokens SHALL define the colors canvas `#0D0C0F`, card `#15131A`, active-card `#1C1924`, terminal `#080C0A`, gold `#D4AF37`, phosphor `#39FF14`, violet `#A855F7`, decay `#EF4444`, parchment `#F3EFE6` and muted `#A39E93`, each as a six-digit hexadecimal value.
2. THE Design_Tokens SHALL keep the existing token names `--color-ink`, `--color-parchment`, `--color-gold`, `--color-terminal-bg`, `--color-phosphor`, `--color-decay-red`, `--color-ai-violet`, and declare each in the form `--color-<name>: <hex>;` that `theme.test.ts` matches, with exactly one declaration per name.
3. WHEN a color value in `global.css` changes, THE Theme_Mirror SHALL contain the same value for that color in the same change, and `theme.test.ts` SHALL fail if any mirrored color differs from its `global.css` value.
4. THE Frontend SHALL ensure each text pair in `contrast.test.ts` has a contrast ratio of at least 4.5:1 and each UI pair in `contrast.test.ts` has a contrast ratio of at least 3:1, calculated with the WCAG 2.x relative luminance formula.
5. IF a Stitch color fails the required contrast ratio against its background, THEN THE Design_Tokens SHALL use the nearest lighter or darker value that meets the required ratio, and `design.md` SHALL record the token name, original value, replacement value and resulting ratio.
6. WHERE the Stitch muted text color `#A39E93` is used for text, THE Frontend SHALL render it only on backgrounds where its contrast ratio is at least 4.5:1.
7. THE Design_Tokens SHALL declare a border radius of `0` for inputs, buttons, cards, chips and progress tracks.
8. THE Design_Tokens SHALL declare the Stitch spacing scale: `space-xs` 0.25rem, `space-sm` 0.5rem, `space-md` 1rem, `space-lg` 1.5rem, `space-xl` 2.5rem, gutter 1.5rem, margin 2.5rem and margin-mobile 1rem.
9. THE Design_Tokens SHALL declare elevation values for four levels: Level 0 canvas with no border and no shadow, Level 1 card with a `rgba(212, 175, 55, 0.30)` border, Level 2 active with a `rgba(212, 175, 55, 0.60)` border and a `0 8px 32px -4px rgba(212, 175, 55, 0.08)` glow, and Level 3 terminal with an inset shadow.

### Requirement 5: Logical properties and bidirectional layout

**User Story:** As an Arabic-speaking user, I want the redesigned layout to mirror correctly in right-to-left mode, so that both languages have equal quality.

#### Acceptance Criteria

1. THE Frontend SHALL contain zero occurrences of Physical_Utilities in any file under `frontend/src/`, and SHALL pass `i18n.property.test.ts` and the logical-spacing check in `_layout.test.ts` with zero failures.
2. WHEN the Stitch_Design uses `left-0`, `right-0`, `ml-*`, `mr-*`, `pl-*`, `pr-*`, `text-left` or `text-right`, THE Frontend SHALL use the corresponding `start-0`, `end-0`, `ms-*`, `me-*`, `ps-*`, `pe-*`, `text-start` or `text-end` in place of each, with the same spacing value suffix.
3. WHILE the document direction is `rtl`, THE Frontend SHALL render the header layout, nav item order, single-side borders and directional icons (arrows and chevrons) as the horizontal mirror image of their `ltr` rendering.
4. THE Frontend SHALL write all directional CSS in `global.css` using logical properties (`margin-inline-*`, `padding-inline-*`, `inset-inline-*`, `border-inline-*`, `text-align: start`), with zero physical-direction properties (`margin-left`, `margin-right`, `padding-left`, `padding-right`, `left`, `right`, `border-left`, `border-right`, `text-align: left`, `text-align: right`).
5. WHEN a record title, summary or user-supplied text is rendered, THE Frontend SHALL set `dir="auto"` on the element containing that text.
6. WHEN a page that had `dir="auto"` on an element before the redesign (for example `id="chamber-title"`) is rendered after the redesign, THE Frontend SHALL keep `dir="auto"` on that same element.
7. IF a Physical_Utility or physical-direction CSS property is found in `frontend/src/` by `i18n.property.test.ts` or `_layout.test.ts`, THEN THE Frontend test run SHALL fail and report the file path and the offending token.

### Requirement 6: Isolate MARC and terminal text direction

**User Story:** As an archivist, I want MARC and terminal text always left-to-right, so that tags, indicators and subfield codes stay readable in Arabic mode.

#### Acceptance Criteria

1. THE Frontend SHALL render every Marc_Surface with `direction: ltr` and `unicode-bidi: isolate`, defined in `global.css`, in both `ltr` and `rtl` document direction.
2. THE TerminalPanel SHALL keep the attributes `dir="ltr"` and `lang="und"` and the classes `terminal marc-text` on its output element, matching the pattern tested in `_layout.test.ts`.
3. THE Frontend SHALL use IBM Plex Mono as the first font-family entry for every Marc_Surface, followed by a generic `monospace` fallback.
4. THE Frontend SHALL style Marc_Surface elements with the Level 3 terminal surface (background `#080C0A`, phosphor inner glow) and a border-radius of 0.
5. WHILE the document direction is `rtl`, THE Frontend SHALL align the text of each Marc_Surface to the left edge of its container (the line start of its own LTR direction).
6. IF IBM Plex Mono fails to load, THEN THE Frontend SHALL render the Marc_Surface in the `monospace` fallback, keeping `direction: ltr` and left alignment unchanged.
7. WHEN a Marc_Surface contains Arabic or other RTL characters, THE Frontend SHALL keep tags, indicators and subfield codes in the same left-to-right order as in a Marc_Surface containing only Latin characters.

### Requirement 7: Global shell, header and base layout

**User Story:** As a visitor, I want a consistent Stitch-style header and page shell on every page, so that the site feels unified.

#### Acceptance Criteria

1. THE BaseLayout SHALL apply the canvas background, parchment text color, and Stitch body typography to every page rendered by the Frontend.
2. WHILE the viewport width is 768px or wider, THE Header SHALL render as a fixed bar of exactly 80px height with a canvas background (`#0D0C0F`) at 95% opacity, a backdrop blur, and a 1px bottom border.
3. THE Header SHALL render the brand block as a gold-bordered square icon tile followed by the "NecroMARC" wordmark in EB Garamond gold.
4. THE Header SHALL render navigation items in uppercase with letter spacing.
5. WHILE a nav item matches the current page, THE Header SHALL render that item in primary gold with a 2px bottom border and a soft gold glow, and SHALL set `aria-current` on it as it did before the redesign.
6. THE Header SHALL render the language toggle as a bordered control with zero border radius.
7. THE Header SHALL render the Judge Login control as a gold-bordered button.
8. WHEN the pointer hovers over the Judge Login control, THE Header SHALL fill the button background with gold.
9. WHILE the viewport width is narrower than 768px, THE Header SHALL keep every navigation entry that was visible before the redesign reachable, by wrapping or stacking entries, with no entry hidden or clipped.
10. WHILE the Header is fixed, THE BaseLayout SHALL offset page content so that the top edge of the first content element is at or below the bottom edge of the Header at every viewport width from 320px upward.
11. THE Frontend SHALL render a gold focus outline of at least 2px width on every interactive element when it receives keyboard focus.
12. WHERE the user agent reports `prefers-reduced-motion: reduce`, THE Frontend SHALL disable all transform transitions and glow transitions, so that those property changes apply instantly (0ms duration).

### Requirement 8: Home and Archive pages

**User Story:** As a visitor, I want the archive listing to use the Stitch catalog layout, so that I can browse resurrected records and see their health at a glance.

#### Acceptance Criteria

1. THE Archive SHALL render each record card as a Level 1 surface with a 1px gold hairline border and a border radius of 0.
2. THE Archive SHALL render each card title in EB Garamond gold, each metadata value in the interface sans face in muted parchment, and each numeric telemetry value in IBM Plex Mono.
3. THE Archive SHALL render each subject entry as a gold chip, each AI-generated marker as a violet provenance badge, and each decay indicator as a crimson decay tag.
4. THE Archive SHALL render each vitality indicator as a 6px-high recessed track with a phosphor fill and a bloom effect, and SHALL retain the existing `role="meter"` attribute and the existing `aria-valuemin`, `aria-valuemax` and `aria-valuenow` attributes with unchanged values.
5. THE Archive SHALL render each filter control and the search input with the canvas background color and a 1px border of gold at 30% opacity.
6. WHEN a filter control or the search input receives focus, THE Archive SHALL change its border to solid gold and display an ambient glow around it.
7. WHILE the viewport width is below 768px, THE Archive SHALL lay out cards in 1 column.
8. WHILE the viewport width is from 768px to 1279px, THE Archive SHALL lay out cards in 2 columns.
9. WHILE the viewport width is 1280px or greater, THE Archive SHALL lay out cards in 3 columns.
10. THE Archive SHALL set the grid `gap` between cards equal to the gutter spacing token value at every viewport width.
11. THE Archive SHALL preserve the pagination, filtering, sorting and empty-state elements, with each element's existing id unchanged and each element in the same relative DOM order as before the restyle.
12. IF the archive query returns zero records, THEN THE Archive SHALL display the empty-state element in place of the card grid, and SHALL keep the filter controls and search input visible and enabled.
13. THE `index.astro` page SHALL compose the Archive and any existing landing content using the new shell and spacing, and SHALL keep its existing logic imports unchanged, with no imports added or removed.

### Requirement 9: Resurrection Chamber page

**User Story:** As a judge or archivist, I want the Chamber as a Stitch two-column workstation, so that I can inspect source MARC beside the resurrected record.

#### Acceptance Criteria

1. THE Chamber page SHALL keep the classes `grid-cols-1 md:grid-cols-2` and `min-w-0` on its two-column container, so that `_layout.test.ts` passes.
2. WHEN the viewport width is 375px, THE Chamber page SHALL render the two-column container as a single column with no horizontal page scrolling.
3. WHERE the viewport width is 1280px or wider, THE Chamber page MAY render columns in a 5:7 or 6:6 ratio, provided the class strings required by criterion 1 remain present.
4. THE TerminalPanel SHALL render as a Level 3 recessed viewport with a header strip and phosphor-colored text.
5. WHEN the TerminalPanel output exceeds the panel's visible height, THE TerminalPanel SHALL display a vertical scroll region that keeps the header strip visible and lets the user scroll to the first and last lines of output.
6. THE ResurrectedCard SHALL render as a Level 2 surface with a gold 60% opacity border and an ambient glow, showing the title, summary, topic chips and AI provenance badge in the styles defined in Requirement 8.
7. IF the resurrected record lacks a summary or topic chips, THEN THE ResurrectedCard SHALL omit the missing element, still render the title and AI provenance badge, and show no empty placeholder or error.
8. THE DecayBreakdown SHALL render each contributing factor as a crimson-tagged row with its numeric value in a monospace font, and SHALL render a vitality gauge in phosphor or crimson, keeping its existing data attributes and slots.
9. IF the DecayBreakdown receives no contributing factors, THEN THE DecayBreakdown SHALL render the vitality gauge with zero factor rows and no error.
10. THE ExportButtons SHALL render as ghost buttons with a transparent background, muted text, and a gold 20% opacity border.
11. WHEN the user hovers over an ExportButtons button, THE ExportButtons SHALL change that button's border to gold 50% opacity and its text to parchment.
12. THE Chamber page SHALL render the Resurrect action as a terminal-action button with terminal background, phosphor text, and a phosphor 60% opacity border.
13. WHEN the user hovers over the Resurrect action, THE Chamber page SHALL apply a phosphor glow to the button.
14. WHILE the user is not a Judge, THE Chamber page SHALL keep `chamber-resurrect` hidden and `chamber-guest` visible per the existing script.
15. THE Chamber page SHALL keep `import.meta.env.BASE_URL` link construction (`href={`${base}/`}` and `${base}/chamber/?id=`) as asserted in `_layout.test.ts`.

### Requirement 10: Summon page, Uploader and Login modal

**User Story:** As a judge, I want the upload and login flows to match the new look, so that protected actions feel consistent with the rest of the site.

#### Acceptance Criteria

1. THE Uploader SHALL render its drop zone as a Level 1 surface with a 1px dashed gold border.
2. WHILE a file is dragged over the drop zone, THE Uploader SHALL render the drop zone with a 1px solid gold border and a Level 2 glow, using the existing drag-state class or attribute.
3. WHEN the file is dropped or the drag leaves the drop zone, THE Uploader SHALL restore the dashed gold border and Level 1 surface within 100 ms.
4. THE Uploader SHALL render its progress, status and error areas using the telemetry styles, and SHALL keep the existing `aria-live` attributes, `aria-busy` attributes and element ids unchanged.
5. THE Uploader SHALL render primary actions as Stitch primary buttons with a card background, gold text and gold border, and with a gold fill on hover and keyboard focus.
6. THE LoginModal SHALL render as a Level 2 dialog with zero border radius over a backdrop dimmed to 60% to 80% black opacity.
7. THE LoginModal SHALL render each input with a visible associated label, styled per Requirement 8.5, and SHALL render its submit action as a Stitch primary button.
8. WHEN the `login:open` event is dispatched, THE LoginModal SHALL open, move focus to the first focusable element inside the dialog, and keep Tab and Shift+Tab focus cycling within the dialog using the existing focus-trap logic.
9. THE LoginModal SHALL keep the existing `role="dialog"` and `aria-modal` attributes unchanged.
10. IF an authentication error is shown, THEN THE LoginModal SHALL render it as a crimson decay tag, keep the existing `role` or `aria-live` attribute, keep the entered username value, and clear the password field.
11. THE `summon/index.astro` page SHALL present the Uploader inside the new page shell, with the page title in the Stitch title typography.

### Requirement 11: Graph page, semantic search, canvas and legend

**User Story:** As a researcher, I want the graph view and semantic search to share the Stitch inspector style, so that exploring relationships is visually coherent.

#### Acceptance Criteria

1. THE SemanticSearch SHALL render its input and results as Stitch form controls and Level 1 result cards, keeping every existing element id, `data-slot` target and `aria-live` region unchanged in name, count and DOM presence.
2. THE Legend SHALL render as a dark card containing three line-style swatches, each with a 1px line thickness: a solid line for Shared Subject, a dashed line for Same Era and a dotted line for Semantic Similarity, plus one neon dot for each node type.
3. THE Legend SHALL keep every existing `data-i18n` key unchanged and SHALL keep `graph:filters` and `graph:clear` as the names of the events it dispatches.
4. WHEN a user toggles a legend filter or activates clear, THE Legend SHALL dispatch the corresponding `graph:filters` or `graph:clear` event exactly once per interaction, with the same payload shape as before the restyle.
5. THE GraphCanvas SHALL render inside a Level 3 recessed container with a 1px gold hairline border, keeping the container id used by the cytoscape initialisation and the container's existing minimum height unchanged.
6. THE Frontend SHALL NOT modify cytoscape style objects, node and edge data mapping, or layout options in `graph.ts` or in inline scripts.
7. WHERE the viewport width is 1280px or more, THE graph page MAY render the legend and search panel beside the canvas.
8. WHILE the viewport width is less than 1280px, THE graph page SHALL stack the legend and search panel above the canvas, with no horizontal scrollbar on the page.
9. IF the semantic search request fails or returns zero results, THEN THE SemanticSearch SHALL display a Level 1 message card in the existing `aria-live` region indicating the failure or the empty result, and SHALL preserve the text in the input field.

### Requirement 12: Accessibility and responsiveness

**User Story:** As a user on any device or assistive technology, I want the redesigned interface to remain accessible, so that the visual change does not reduce usability.

#### Acceptance Criteria

1. WHEN any Frontend page is rendered at a viewport width of 375px, 768px or 1280px, THE Frontend SHALL display all page content with a document scroll width less than or equal to the viewport width, so that no horizontal scrolling is required.
2. WHILE the viewport width is less than 768px, THE Frontend SHALL render every button, toggle and nav link with a clickable area of at least 44px by 44px.
3. WHEN any Frontend page is rendered, THE Frontend SHALL include exactly one `header`, at least one `nav`, exactly one `main` and exactly one `footer` landmark, and SHALL keep the heading levels (h1 to h6) in the same relative order and nesting as before the redesign, with exactly one h1 and no skipped levels.
4. WHEN any Frontend page is rendered, THE Frontend SHALL set the `lang` and `dir` attributes on the document root through BaseLayout and the initial i18n script, so that the values match the active language (`dir="rtl"` for Arabic and `dir="ltr"` for English) before the first paint.
5. IF the user changes the language, THEN THE Frontend SHALL update the `lang` and `dir` attributes on the document root within 100 ms and SHALL preserve the user's current page and scroll position.
6. THE Frontend SHALL convey the state of each decay, vitality and provenance indicator with a visible text label or a distinct shape or pattern in addition to color, so that each state is distinguishable when the page is rendered in grayscale.

### Requirement 13: Build, static output and verification

**User Story:** As a release owner, I want the redesign to pass every existing gate, so that it ships without regressions.

#### Acceptance Criteria

1. WHEN `npm test` runs in `frontend/`, THE Test_Suite SHALL execute all 124 tests, including `components.dom.test.ts`, `chamber.dom.test.ts`, `theme.test.ts`, `contrast.test.ts`, `i18n.property.test.ts` and `_layout.test.ts`, with 124 passed, 0 failed, 0 skipped and exit code 0.
2. WHEN `npm run check:i18n` runs, THE Frontend SHALL exit with code 0 and report 0 missing keys and 0 unused keys.
3. WHEN `PUBLIC_BASE_PATH=/necromarc PUBLIC_API_URL=https://3aai.in/necromarc/api npm run check:bundle` runs, THE Frontend SHALL build with `output: 'static'`, emit every internal link and asset URL prefixed with `/necromarc`, and exit with code 0.
4. WHEN the bundle scan in `npm run check:bundle` completes, THE Frontend SHALL report 0 secret-pattern matches in the built output.
5. THE Frontend SHALL contain 0 occurrences of API keys, service-role keys or Judge passwords, including the values of `OPENROUTER_API_KEY`, `GEMINI_API_KEY`, `SUPABASE_SERVICE_ROLE_KEY` and `JUDGE_ACCESS_PASSWORD`, in any file changed by the redesign.
6. THE Frontend SHALL declare none of `torch`, `pytorch`, `tensorflow`, `transformers`, `sentence-transformers` or `ollama` as a dependency in any dependency manifest or lockfile it changes.
7. THE Frontend SHALL keep the `/.kiro/` directory tracked by git, with no `.gitignore` entry that matches `/.kiro/` or any path beneath it.
8. IF a Verification_Command exits with a non-zero code, THEN THE Frontend SHALL be corrected by editing only the In_Scope_Files, and the failed command SHALL be re-run to exit code 0 before the redesign is considered complete.
