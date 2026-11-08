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

## Theme 2: Glass Janus (was Glass; plain, no Halloween)
iOS-style layered glass, for users who prefer a neutral health app. Vocabulary: "possible prescribing cascade" (not ghost), "Patient / Research" sections (not mask), a plain "Retracted" label (not a stamp), "evidence summary" (not séance).
- Soft background of three blurred colour fields (mint `#CFE9E3`, sand `#F3E3CC`, sky `#DCE6F2`) on `#EEF1F0`, fixed to the viewport on pages of any length; cards are frosted glass at **at least 72 % opacity** with `backdrop-filter: blur(22px) saturate(1.6)`, 26 px radius, 1 px white inner edge; floating pill tab bar (Scan, Medicines, Results, Settings); round glass icon buttons.
- **`prefers-reduced-transparency: reduce` or the in-app "Reduce transparency" setting** → solid cards (`#FFFFFF` light, `#1C1F22` dark) and no blur. Same for devices where `backdrop-filter` is unsupported.
- Tokens (light / dark): `--bg #EEF1F0 / #0E1514`, `--surface rgba(255,255,255,.72) / rgba(28,31,34,.78)`, `--fg #0E1514 / #EEF3F2`, `--muted #4F5B59 / #A9B6B3`, `--line rgba(14,21,20,.12) / rgba(255,255,255,.12)`, `--accent #0B6C62 / #6FD3C4`, `--on-accent #FFFFFF / #062B27`, `--warn #8A4B00 / #FFC266`, `--risk #B3261E / #FF7B72`.
- Type: system UI first (`-apple-system, "SF Pro Text"`), then **Figtree**; display 32 px large titles; IBM Plex Mono for codes.

## Home scenes (owner decision 2026-11-08; experience Req 27.6, DP46)
Each theme has its own cinematic home; every other screen keeps the tokens above. Assets: `apps/web/public/home` (AI-generated for Janus, provenance in its README and `NOTICE`).
- **Night Pharmacy** (owner decision 2026-11-08, third, DP49: nothing is driven by scroll) — one stage, three scenes: (1) the isometric night pharmacy (focal point on the house, the phone crop centres it), headline, sub-headline, "Try the demo", "How it works" as real text in the left third over a scrim, and under them a clear **"Step inside"** button with a play icon and a small animated scroll-down cue below it (same action); pointer parallax on three layers (sky, house, mist), DOM fireflies; 3–4 code-made ghosts rise out of the shop windows (2 on phones; desktop ghosts 3.5 % of the image width with a slightly stronger glow). (2) "Step inside" plays the door video once, full-bleed, at normal speed, with a short Skip control. (3) At its end it cross-fades into the medicine cabinet in place and focus moves to the scene 3 heading: the ghosts hover as the Istanbul demo's findings (each a button into the demo, keyboard focusable, accessible name), the glowing note becomes "Prepare the doctor note", and Replay plays the way in again. Then the normal home sections.
- **Ghost** (`components/Ghost.tsx`, one component for the home and the findings): soft glowing mist body, teal edge `#7FD1C7`, two eyes, a wavy tail; idle float, tail wave, occasional blink, a curious lean toward the pointer. Never scary; always `aria-hidden`, the text next to it carries the meaning.
- **Glass Janus** — the glass two-faced head full-bleed, headline and actions on the left over a scrim, a slow light sweep across the glass (a band moved by transform), tiny floating capsule highlights, gentle parallax and a 3° tilt on pointer move. No ghosts, no Halloween, nothing driven by scroll.
- **Smooth scrolling** (DP49): no pinned or sticky sections, no scroll listener doing per-frame work, no layout reads in animation loops; ambient motion animates transform and opacity only and pauses off-screen and in a hidden tab. Measured: no long task over 50 ms while scrolling the home at 1440 and 375 px.
- **Rules**: `prefers-reduced-motion`, Save-Data, a slow connection or a video that cannot play → no parallax, no drift, still ghosts, and "Step inside" cross-fades straight to the cabinet without the video. The LCP image is preloaded at the right size for the active theme only; the video (with its poster) is attached only once the page is idle; the hero motion is its own chunk; no layout shift. Text contrast ≥ 4.5:1 over images (gradient scrim); alt texts in five languages; the video is decorative; focus order hero → step inside → findings. The emergency notice and the disclaimer stay on the home: on the home the notice is a one-line bar under the transparent header (expandable to the full text), so the hero fills the first viewport (DP47).

## Shared rules (both themes)
- **Red (`--risk`) only for real risk**: emergency notice, urgent-care lines, retracted evidence. Never for a finding, a ratio, or an assessment class.
- **Assessments** (`disproportionate`, `weak`, …) appear only in a detail view with range and report count; never as a badge, colour or icon in a list (collective-memory display rules).
- **Ratios** are drawn with a confidence-interval bar: axis, a mark at 1 ("no difference"), the range, the point estimate. Text gives the same numbers.
- **Contrast** ≥ 4.5:1 for text, ≥ 3:1 for UI boundaries and focus; verified by a test over every token pair that is used as text-on-surface in both themes and both colour schemes.
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
- Tailwind CSS v4 with CSS variables per theme: `:root[data-theme-style="two-faces"]`, `.paper`, `:root[data-theme-style="glass"]` plus `prefers-color-scheme` for Glass light/dark. Components use tokens only, never raw hex.
- Theme, large text, reduce transparency, read aloud: stored in `localStorage` (per-device convenience), read before first paint to avoid a flash.
- Reference mockups: `docs/design/` (static HTML of the chosen screens).
