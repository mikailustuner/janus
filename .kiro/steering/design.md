---
inclusion: fileMatch
fileMatchPattern: "apps/web/**"
---

# Design system (owner decision 2026-11-08)

Chosen with the `ui-ux-pro-max` skill from seven presented directions. Two themes, one component set. The user switches them in **Settings › Appearance**; the default is **Night Pharmacy**. Owner decision 2026-11-08 (second): the themes are named **Night Pharmacy** (was Two Faces) and **Glass Janus** (was Glass); internal ids stay `two-faces` and `glass`. Content, safety rules and layout are identical in both themes; only the vocabulary of the theme devices and the visual tokens change.

## Theme 1 (default): Night Pharmacy (was Two Faces)
**Owner decision 2026-11-08 (third): no light mode** (experience DP48). One dark set on every screen, the researcher area included: midnight indigo background, ivory text. There is no shadow / light face and no mask switch; "Research" is an entry of the header navigation (both themes), the footer and Settings, so a patient never lands on it by surprise.
- **Paper** (ivory, midnight text): the doctor note preview, the doctor QR page form (a paper card on the Night Pharmacy page: it reads like the printed note and stays legible on a phone in a bright room) and the demo doctor form, in every theme. The doctor note PDF is printed on white paper with the same text colours.
- Theme devices are functional (product.md): **ghost** = a cascade finding; **zombie stamp** = retracted evidence that was not used; **séance table** = the three-witness view; the two-faced **mask** is the Janus mark only. No decorative-only spooky elements.

| Token | Night Pharmacy | Paper (note preview, doctor page card; PDF text on white) |
|---|---|---|
| `--bg` | `#1B1F3B` | `#F6F1E7` |
| `--surface` (cards) | `#252A4D` | `#FFFDF8` |
| `--fg` | `#F6F1E7` | `#1B1F3B` |
| `--muted` | `#C3C2D6` | `#4E5170` |
| `--line` | `#3A4070` | `#DDD5C4` |
| `--accent` | `#7FD1C7` | `#1E6B62` |
| `--on-accent` | `#0E2A27` | `#FFFFFF` |
| `--chip` / `--chip-fg` | `#2F3A5E` / `#A9E4DC` | `#E7EFEA` / `#1E6B62` |
| `--warn` (abrupt-stop line, cautions) | `#F6D08A` | `#7A4D00` |
| `--risk` (real risk, retracted stamp, emergency only) | `#FF8A80` | `#A8322D` |
| `--ghost` | `#F6F1E7` | `#1B1F3B` |

Type: **Fraunces** (display, headings) and **Atkinson Hyperlegible** (all running text, labels, controls, the large-text mode; chosen for low-vision legibility, Option 2's rule). **IBM Plex Mono** for ATC codes, DOIs, ratios and ranges (`font-variant-numeric: tabular-nums`). Radius 16 px cards, 999 px chips, 14 px buttons.

## Theme 2: Glass Janus (was Glass; plain, no Halloween) — Clinical White (owner decision 2026-11-09)
**Owner decision 2026-11-09: Glass Janus becomes "Clinical White"** (experience Req 31, DP66–DP72), from the owner-approved design canvas (home, results and finding detail, phone medicines list). The name stays **Glass Janus** / **Cam Janus**, the id stays `glass`. **Light only** (owner decision 2026-11-09): Glass has no dark variant and does not follow `prefers-color-scheme`. Vocabulary unchanged: "possible prescribing cascade" (not ghost), a plain "Retracted" label (not a stamp), "evidence summary" (not séance).
- Ground `#F4F7F8`, **solid white cards** (`#FFFFFF`) with a 1 px hairline (`#E3E8EA`) and soft layered shadows; no colour fields behind the page. **Glass (frosted) only for navigation and floating controls**: the header bar, the header navigation on the home, the floating pill tab bar (Scan, Medicines, Passport, Results, Settings) and floating hero cards: white at 86–88 % opacity with `backdrop-filter: blur(20px) saturate(1.6)`.
- **`prefers-reduced-transparency: reduce`, the in-app "Reduce transparency" setting or no `backdrop-filter`** → solid white navigation and controls, no blur (cards are solid already).
- Tokens: `--bg #F4F7F8`, `--surface #FFFFFF`, `--fg #0E1A1F`, `--muted #5A686E`, `--line #E3E8EA`, `--accent #0B6C62`, `--on-accent #FFFFFF`, `--chip #E6F2F0` (mint tint) / `--chip-fg #0B5A52`, `--warn #8A4B00`, `--risk #B3261E` (unchanged: real risk only), `--nav-surface rgba(255,255,255,.88)`, `--nav-blur blur(20px) saturate(1.6)`.
- Radii as the canvas: cards 22 px, groups 18 px, tiles 16 px, buttons 14 px, segments 12 px, tab bar 26 px (items 20 px).
- Type: **Figtree** (display and text, 800 for large titles, −0.02 em), then the system UI; IBM Plex Mono for codes and figures in tiles.

## Home scenes (owner decision 2026-11-08; experience Req 27.6, DP46)
Each theme has its own cinematic home; every other screen keeps the tokens above. Assets: `apps/web/public/home` (AI-generated for Janus, provenance in its README and `NOTICE`).
- **Night Pharmacy** (owner decision 2026-11-08, third, DP49: nothing is driven by scroll) — one stage, three scenes: (1) the isometric night pharmacy (focal point on the house, the phone crop centres it), headline, sub-headline, "Try the demo", "How it works" as real text in the left third over a scrim, and under them a clear **"Step inside"** button with a play icon and a small animated scroll-down cue below it (same action); pointer parallax on three layers (sky, house, mist), DOM fireflies; 3–4 code-made ghosts rise out of the shop windows (2 on phones; desktop ghosts 3.5 % of the image width with a slightly stronger glow). (2) "Step inside" plays the door video once, full-bleed, at normal speed, with a short Skip control. (3) At its end it cross-fades into the medicine cabinet in place and focus moves to the scene 3 heading: the ghosts hover as the Istanbul demo's findings (each a button into the demo, keyboard focusable, accessible name), the glowing note becomes "Prepare the doctor note", and Replay plays the way in again. Then the normal home sections.
- **Ghost** (`components/Ghost.tsx`, one component for the home and the findings): soft glowing mist body, teal edge `#7FD1C7`, two eyes, a wavy tail; idle float, tail wave, occasional blink, a curious lean toward the pointer. Never scary; always `aria-hidden`, the text next to it carries the meaning.
- **Glass Janus** (Clinical White, owner decision 2026-11-09, DP68–DP70) — the clinical hero image (a clear glass two-faced head filled with capsules on a white studio ground) full-bleed **at its own aspect ratio (2752 × 1536), never cropped**, nothing over the two faces; the copy in dark ink in the light left area (only a light left-edge scrim); two frosted, perspective-tilted, floating cards on the right (the Istanbul demo's amlodipine → furosemide finding with its real figures, and the 65 checked patterns with "photos stay on this device"); CSS-drawn 3D capsules (two-tone halves, specular highlight, shadow, some slightly blurred) floating outside the faces; a slow light sweep. Then "At a glance" (a bento grid: a tilted phone showing a results screen, a tilted doctor-note paper with a QR code, a dark "65" tile, the TR / EU / US source cards fanned out, a "checked against Crossref" badge; no invented number), "How it works" with 3D icon chips, privacy, footer. Below 1,100 px the image sits on top at full width under the header and the emergency bar, the copy below on white, the floating cards and capsules are hidden and the grid is one column (below 960 px). No ghosts, no Halloween, nothing driven by scroll.
- **Smooth scrolling** (DP49): no pinned or sticky sections, no scroll listener doing per-frame work, no layout reads in animation loops; ambient motion animates transform and opacity only and pauses off-screen and in a hidden tab. Measured: no long task over 50 ms while scrolling the home at 1440 and 375 px.
- **Rules**: `prefers-reduced-motion`, Save-Data, a slow connection or a video that cannot play → no parallax, no drift, still ghosts, and "Step inside" cross-fades straight to the cabinet without the video. The LCP image is preloaded at the right size for the active theme only; the video (with its poster) is attached only once the page is idle; the hero motion is its own chunk; no layout shift. Text contrast ≥ 4.5:1 over images (gradient scrim); alt texts in five languages; the video is decorative; focus order hero → step inside → findings. The emergency notice and the disclaimer stay on the home: on the home the notice is a one-line bar under the transparent header (expandable to the full text), so the hero fills the first viewport (DP47).

## Cards and layout system (owner request 2026-11-09; experience Req 29, DP50–DP56)
Apple Health / Settings style, chosen with the `ui-ux-pro-max` skill (inset grouped lists, stat tiles, glass only for navigation and controls). Primitives live in `apps/web/src/components/cards/`; screens use them instead of hand-made cards.
- **Spacing scale** (tokens in `tokens.css`, Tailwind `p-row-x`, `gap-group` …): row padding 16 px × 12 px, stack 12 px inside a card, 24 px between groups, 32 px between page sections; page gutter 16 px (phone), the shell's 720 / 1,120 px widths unchanged.
- **Radius tokens:** `--radius-card` (16 / 22 px), `--radius-group` (16 / 18 px), `--radius-tile` (14 / 16 px), `--radius-segment` (12 / 12 px), `--radius-button` (14 / 14 px); Night Pharmacy / Glass Janus (Clinical White radii since 2026-11-09).
- **Grouped lists:** items of one kind (medicines, sources, countries, regions, rules) are rows of one rounded group; rows ≥ 44 px, hairline separators (`--line`, 1 px) inset from the leading edge, never on the first row; a short section header above the group (`--muted`, semibold, sentence case) and an optional footer under it (`--muted`, small) for attributions and notes. A row that navigates is one link with a chevron.
- **Summary-line rule:** every screen has one large title (`h1`, `--large-title`); a card or page may have one summary line under its title (one sentence, `--muted`), e.g. "Listed in 3 of 4 countries", "4 possible prescribing cascades · 9 medicines checked". A summary never replaces a required sentence.
- **Big-number rule:** when a number is the main fact of a card (reports of a pair, sources checked, patterns checked, witnesses), show it as a stat tile (large tabular figure + short label); the full sentence stays in the tile for screen readers and stays visible where a requirement names it (integrity line, caveats `spontaneous_reporting` / `not_incidence`, weak-pattern label). Ratios always with their range and the CI bar. No assessment in a tile, row header or segment; no `--risk` in a tile.
- **Disclosure and segmented controls:** folded detail uses `<details>`/`<summary>` with a chevron; choices between a few views use a segmented control of native radios (pills when the options are many or long). A filter defaults to showing everything.
- **Motion rule:** transform and opacity only; 150 ms (press, chevron), 220 ms (disclosure opening), 240 ms (page enter after a client navigation, not on first load, not on the home); `--ease-out`; nothing under `prefers-reduced-motion: reduce`.

## Shared rules (both themes)
- **Red (`--risk`) only for real risk**: emergency notice, urgent-care lines, retracted evidence. Never for a finding, a ratio, or an assessment class.
- **Assessments** (`disproportionate`, `weak`, …) appear only in a detail view with range and report count; never as a badge, colour or icon in a list (collective-memory display rules).
- **Ratios** are drawn with a confidence-interval bar: axis, a mark at 1 ("no difference"), the range, the point estimate. Text gives the same numbers.
- **Contrast** ≥ 4.5:1 for text, ≥ 3:1 for UI boundaries and focus; verified by a test over every token pair that is used as text-on-surface in both themes (Night Pharmacy dark, Glass Janus light), with reduced transparency on and off.
- **Touch targets** ≥ 44 × 44 px; visible focus ring (3 px `--accent`, 2 px offset); keyboard order follows reading order.
- **Large-text mode**: base 19 px (default 16 px), line height 1.6. **Read aloud**: Web Speech API, findings only, off by default.
- **Motion**: ghosts may drift (6 s, 3 px) in Night Pharmacy only (the home scenes allow more, above); everything else 150–250 ms. `prefers-reduced-motion: reduce` stops all non-essential motion.
- **Layout**: mobile first, checked at 375 px and 1280 px; no horizontal scroll; max content width 720 px on desktop for reading screens.
- **Icons**: inline SVG (Lucide shapes, 1.9 px stroke); never emoji.
- **Medicine icons** combine shape and colour so they work for colour-blind users.
- **Every data view** has loading, empty, error and long-content states.
- **Disclaimer** (medical-safety rule 9) on every screen; the emergency notice first wherever a rule 10 symptom or an urgent-care line appears.
- **Demo data** shows a persistent "Demo · synthetic patient" label on every screen.

## Implementation
- Tailwind CSS v4 with CSS variables per theme: `:root[data-theme-style="two-faces"]`, `.paper`, `:root[data-theme-style="glass"]` (light only since 2026-11-09; no `prefers-color-scheme` rule). Components use tokens only, never raw hex.
- Theme, large text, reduce transparency, read aloud: stored in `localStorage` (per-device convenience), read before first paint to avoid a flash.
- Reference mockups: `docs/design/` (static HTML of the chosen screens).
