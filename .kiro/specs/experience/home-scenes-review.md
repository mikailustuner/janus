# Review: theme names and cinematic homes (owner decision 2026-11-08, DP46)

**Passes:** localization-reviewer and safety-auditor (`.kiro/agents`), two separate read-only agent passes on every new or
changed message row (theme names and hints, `Home.*` hero, scene 3, ghost labels, alt texts) and on the home code.

## Localization: 0 blocking, 5 advisory (all applied)

| Key | Lang | Finding | Applied |
|---|---|---|---|
| `Home.scene3Intro.twoFaces` | de | "eines" for "Geist" (masculine) | "Öffnen Sie einen …" |
| `Home.ghosts.pipc12` | all | "added" hints an order the label says is unknown | "Trouble sleeping and a sleeping pill (order not known)" and equivalents |
| `Home.scene3Intro.*` | de | "(Demo Istanbul)" | "(Istanbul-Demo)" |
| `Home.ghosts.pipc5` | de | 21-letter word at 375 px | soft hyphen "Entwässerungs­tablette" |
| `Home.alt.glassHero` | tr | "iki yüzlü" also means hypocritical | "iki yüzü olan …" |

Native check still advised: "müshil" vs "laksatif" (tr), "Entwässerungstablette" and "idrar söktürücü" as plain words for
"water pill".

## Safety audit: 0 blocking, 8 advisory (all applied)

| # | Finding | Applied |
|---|---|---|
| 1 | Phone scrim faded before the title | Scrim holds at 0.88 up to 62 % of the screen height, fades by 92 % |
| 2 | "How it works" section and heading shared the id `how` | Section `how-it-works`; hero links updated |
| 3 | Save-Data / slow connection kept ghost and mist animations; Glass ignored them | `[data-still]` stops every animation; Glass sets `data-still` too |
| 4 | The hidden theme's motion chunk was fetched before hydration | Motion loads only for the active hero (`active` prop) |
| 5 | "Prepare the doctor note" did not say it starts the demo | `Home.prepareDemoNote` ("Prepare the demo doctor note") in five languages |
| 6 | "then" safety rested on hard-coded labels | Unit test asserts the timing of rows 5, 6, 9 (`within_window`) and 12 (`date_unknown`) and no "then" in row 12 |
| 7 | A second animation loop could survive; one failing `<source>` switched to stills | Loop guard; still mode only when `networkState` is `NETWORK_NO_SOURCE` |
| 8 | Stale comments | Updated |

Checked with no finding: forbidden phrases and reassurance in all five languages, demo labelling, rule 10 (emergency notice
first on the home in both themes), rule 9 (disclaimer in the footer), product claims, privacy (same-origin assets only, no
data in the inline preload script, nothing of the hidden theme's images loaded), focus order and accessible names, alt
texts, AI-generated provenance in `NOTICE` and `public/home/README.md`.
