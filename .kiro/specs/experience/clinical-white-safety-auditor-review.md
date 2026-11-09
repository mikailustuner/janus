# Review: Glass Janus "Clinical White" (safety-auditor, Req 31)

**Pass:** `safety-auditor` (`.kiro/agents/safety-auditor.md`), one read-only agent pass (2026-11-09) over the Clinical
White restyle (`aa05caf..HEAD` and the uncommitted home work in `apps/web/src`, `apps/web/messages`), Req 31, DP66–DP72
and design §23, against `medical-safety.md`, `privacy.md`, `product.md`, `data-sources.md` and the steering design rules.

## Findings: 0 blocking, 9 advisory

| # | Where | Rule | Severity | Finding | Applied |
|---|---|---|---|---|---|
| F1 | Hero card, `Home.glass.patterns` | Rule 3 (no false reassurance), rule 5 | advisory | "65 … patterns checked": rows 27 and 57 of the rule base can never match (no ATC code for the marker), so "checked" overstates; the number itself is right | The card reads "65 published prescribing-cascade patterns (PIPC list, 2025)" (`Home.glass.patternsTile`); the `patterns` key is removed in five languages |
| F2 | `Home.glass.sourcesTitle`, `badgeTitle` | Rule 3 (scope) | advisory | Claimed every source; only sources with a DOI are checked (demo finding: 4 sources, 3 checked by DOI) | "Sources with a DOI are checked for retractions." and "DOIs checked against Crossref" in five languages |
| F3 | `Home.glass.noteText` | Privacy (QR opt-in), product truth | advisory | The QR code is opt-in, not on every note | "… and, if you choose, a QR code the doctor can use to answer." in five languages |
| F4 | `Home.glass.regionsText` | Product truth (`data-sources.md`) | advisory | "the EU" reads as the whole EU; product lookup covers France (BDPM) and Spain (CIMA) | "Public medicine lists from Türkiye, France and Spain (EU) and the US." in five languages (also the localization review's last row) |
| F5 | `GlassJanusHero.tsx`, `Home.glass.cards` | Demo labelling (accuracy) | advisory | "From the Istanbul demo" labelled both cards; the second (65 patterns, photo privacy) is not demo data | The label is on the first card only (`role="group"`); the container is a plain `div` |
| F6 | Hero card A | Rule 1 framing | advisory | A demo finding excerpt without "This may be worth discussing with your doctor" (labelled demo, desktop only, not a findings view) | Not changed; left for the owner (option: make the card a link into the demo finding) |
| F7 | `theme/tokens.css` header | Annotation accuracy | advisory | The header still described a light / dark Glass with frosted cards | Comment updated to DP66 / DP67 |
| F8 | `home-scenes.css` `--gj-*`, text over the image | Contrast (Req 31.3) | advisory | Outside the token test; sampled: muted ≥ 4.67:1, accent ≥ 5.10:1 in the copy column between 10 and 80 % of the image height, lower in the bottom 10 % (floor shadow) | The copy starts under the measured header and emergency bar; screenshots at 1,100–1,440 px show the copy's last line on the light floor or page ground; noted in DP68 |
| F9 | DP71 vs `GlassHomeSections.tsx` | Decorative `aria-hidden` | advisory | DP71 called the region cards decorative; the code exposes them (correctly: they carry the region and source names) | DP71 text corrected |

## Checked and clean (auditor)
Figures (P41): `DEMO_FINDING` equals the recorded Istanbul fixture (amlodipine → furosemide, 5 months, 4 sources;
`no_retracted_used` true); `PATTERNS` = 65 equals the vocabulary, `pipc.csv` and `pipc_rules.csv`; the only literal number
in the texts is the PIPC year 2025; "26 sources current" is gone. Demo label on hero card A and in the phone mock-up.
Emergency notice first in `#content` in both themes, never over the faces (e2e checks it). Disclaimer in the footer.
`--risk` only on the emergency bar (the red capsule is decorative, not the token). No forbidden phrase, no reassurance
word, counts framed as reports. No assessment in a tile or badge. Decorative mock-ups `aria-hidden`; the alt text in five
languages. Privacy: "photos stay on this device" is true; no new request, storage or log. Provenance of the hero in
`public/home/README.md`, `NOTICE`, `sources.toml`; TİTCK data not committed. Glass light only (P40); reduced
transparency turns the navigation solid under all three triggers.
