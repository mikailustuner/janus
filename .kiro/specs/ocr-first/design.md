# Design: OCR first — a box from any country

> Requirements in `requirements.md`. Web only (`apps/web`). No API, pipeline or database change.

## 1. Overview
```
scan screen ── code ──► POST /resolve/scan ──► confirm ──(no candidate)──► "other ways": label photo | name
            ├─ label photo ─► recogniser (device) ─► matchIngredients (device) ─► candidates
            │                                              user taps one ─► POST /resolve/search {English name}
            └─ name ───────► POST /resolve/search                                   └─► confirm ─► list
```
Everything left of a request runs in the browser. The device proposes; the API resolves the chosen name with its
full ingredient and product data; the confirm screen is still where a medicine is confirmed.

| Module | Role |
|---|---|
| `scripts/gen-vocabulary.mjs` → `src/vocabulary/ingredient-names.json` | the device list: key → held names (English first), from the accepted glossary rows; covered by the existing parity test |
| `src/scan/ingredient-match.ts` | pure matcher: `fold`, `skeleton`, `editDistance`, `distanceCap`, `buildIndex`, `matchIngredients` |
| `src/scan/ocr-passes.ts` | pure rule for which reading is used (`readLabel`) |
| `src/scan/ocr.ts` | tesseract.js worker, photo size limit and quarter turns on a canvas |
| `src/scan/label-session.ts` | the label result in memory: reducer, `outboundOf` (the only way to a request), external store |
| `src/components/scan/LabelPanel.tsx`, `ScanPage.tsx` | the three ways, the label panel and its states, "other ways" |
| `src/flow/confirm.ts`, `components/confirm/ConfirmPage.tsx` | "other ways" under not-found / no-database / not-supported; chosen ingredient listed first |
| `scripts/ocr-eval-fixtures.mjs`, `src/scan/eval/*` | synthetic label images, recorded text, measurement |

## 2. Flow (Req 1)
- The tab list keeps its three tabs and their accessible names; each tab now carries an icon and has the same
  size (one grid row). Under the page introduction one line states the claim of the Introduction.
- Each panel starts with a lead sentence (`Scan.codeLead`, `Scan.labelLead`, `Scan.typeLead`).
- `Ways` (scan screen) and `otherWays` (confirm screen) are the same two actions: "Photograph the label",
  "Type the ingredient name". On the scan screen they switch the tab; on the confirm screen they link to
  `/scan#label` and `/scan#type`.
- Where they appear: confirm `not_found`, `no_open_database`, `not_supported`; scan messages `unreadable` and
  `nationalCode`; code panel when the camera is refused or missing, no code after 15 s, no code in a photo.
- Home `how1` and Start `intro` carry the any-country sentence with its limit (Latin letters); the label panel
  says that Janus reads Latin letters only and can misread a word. The home coverage section (regions) is unchanged:
  it lists where codes are looked up.

## 3. Matching (Req 3)
### 3.1 Folding
`toLowerCase` → NFKD → combining marks removed → `ı→i`, `ß→ss`, `æ→ae`, `œ→oe`, `ø→o`, `ł→l`, `đ→d`.
`İ` lower-cases to `i` + a combining dot, which the mark removal drops; `I` lower-cases to `i`. So Turkish
capitals, German sharp s and French/Spanish accents all fold to ASCII, and upper case equals lower case.

### 3.2 Skeleton (per folded word)
In this order: `ph→f`, `th→t`, `ch→c`, `y→i`, `w→v`, `c` before `e`/`i` → `s`, `qu→k`, `k→c`, `x→cs`, `z→s`,
`g` before `e`/`i` → `j`, leading `es` before `p`/`t`/`c` → `s`, doubled letters collapsed; then a final `um`/`us`
is dropped from words of 7 letters or more, and a final `a`/`e`/`o` from words of 6 or more.

These are spelling regularities between the languages on boxes, not pharmacology: amlodipine / amlodipin /
amlodipina / amlodipino / amlodypina / amlodipinum share a skeleton; so do hydrochlorothiazide /
hidroklorotiyazid / hidroclorotiazida. Two different ingredients may share a skeleton; then both are candidates
and the user chooses (the rule never merges ingredients). The rules only reach names the device list holds.

### 3.3 Salt words, connectors, stop words
A fixed list of salt, ester and hydrate words in the five languages and Latin (in the source), compared by
skeleton. Connectors (`de`, `d`, `di`, `of`, `als`, `as`, `como`) join a preceding salt to its name for the printed
text. A short stop list of label words (tablet, capsule, contains, children, in the five languages) is never
compared tolerantly.

### 3.4 Algorithm
Per line, tokens are maximal runs of letters and digits. A token of letters with `0`, `1` or `5` inside is read
with `o`, `l`, `s` (a "repaired" token; its candidate is `close`). Left to right:
1. The longest run of 4…1 tokens whose folded text is a held name → `exact`; else whose skeletons are a held
   name's skeletons → `variant`. The tokens are consumed. A one-token salt word that is also a held name is set
   aside and used only if the label gives no other candidate.
2. Else, for one token that is not a salt or stop word: a compound ending in a salt skeleton (stem of 5 letters
   or more) whose stem is a held skeleton → `variant`; the token joined with the next one equal to a held
   skeleton (a name the recogniser split) → `close`, distance 1; else the single-word held skeletons within the
   cap of the token (or of the compound stem), smallest distance only, at most three keys → `close`.
3. Candidates are ordered `exact`, `variant`, `close` (by distance), then as printed; one per key. Keys with the
   same English name are one key.

The printed text of a candidate is the matched tokens extended by up to two salt words after, and before
(directly, or through a connector), cut from the original line.

Distance is optimal string alignment (insert, delete, replace, swap) on skeletons, computed with an early exit at
the cap. Cost: a few hundred tokens × about 3,000 skeletons, well under 50 ms on a phone.

## 4. Reading (Req 4)
- `recognise(image, locale, useful, onProgress)` makes one worker (interface language + English, as before) and
  calls `readLabel`. Each reading uses `rotateAuto` (the recogniser's own small-angle deskew).
- `readLabel`: upright first; done if it is useful (a candidate or an NDC) or its confidence is at least 75; else
  quarter turns 1, 3, 2 in that order, the first useful one wins, else the most confident reading.
- A quarter turn is a canvas rotation of the photo. The recogniser's own `rotateRadians` was tried and rejected:
  it keeps the canvas size and cuts off a non-square photo (measured on the fixtures).
- Photos over 2,600 px on the long side are scaled down on the same canvas (a 12-megapixel photo is slow and
  memory-heavy in WebAssembly). This limit is a guard, not a measured optimum (§8).
- The camera path reuses `startCamera`/`stopCamera`; `captureFrame` draws the current video frame to a PNG.

## 5. Label session and privacy (Req 2, 6)
`LabelState`: `idle | busy{progress, turned} | failed | none | done{result}`; `LabelResult`: candidates, NDC
shapes, words. The state is module memory behind `useSyncExternalStore` (like `flow/pending.ts`): it survives the
round trip to the confirm screen, not a reload. There is no field for a chosen candidate. `deleteEverything`
(Settings) and `startDemo` clear it.

`outboundOf(state, choice, englishNames)` is the only function that turns a result into a request:
- `ingredient` + index → `{search, query: englishNames[key], key}` — the held English name, never label text;
- `ndc` + index → `{ndc}`; `words` + selection → `{search, query: the adjacent words}` (unchanged rule).
Anything else is `null`. `ScanPage.handleSearch(query, key)` sends `POST /resolve/search` (limit 20 for a chosen
ingredient, so the ingredient candidate is not cut off by same-named products) and stores `prefer = key` in the
pending resolution; `confirmView(r, prefer)` lists that ingredient candidate first. A card keeps its `index` in
the resolution; the confirm screen finds the chosen card by that index, never by its place in the list.

What leaves the device is unchanged in kind (`privacy` and `experience` Req 23.2): a search query the user chose.
The privacy page text needs no change. One thing does change and is recorded here: the recognised words and
candidates now stay in memory until the next photo, "remove" or the tab closing, instead of until the scan
screen closes (`experience` DP9 amended).

## 6. Decisions
- **DP-O1 The device proposes, the API resolves.** The device list holds only the accepted glossary names
  (`experience` Req 2.5: names in the client come from the glossary files). The matcher never creates a list item; it
  creates a search. Alternative rejected: shipping every Wikidata ingredient label to the client (names outside
  the glossary, a large download, and a second source of truth for resolution).
- **DP-O2 The request is the English held name.** The API's name index has every ingredient's English name as an
  exact key, so the chosen ingredient is in the answer; the printed words (which may be misread, or personal on a
  pharmacy label) are never sent through the candidate path.
- **DP-O3 No automatic selection, anywhere.** Even one `exact` candidate is a button, and the confirm screen
  still asks. Ordering is the only help.
- **DP-O4 A strict, length-based cap.** 0 / 1 / 2 edits; tolerant matching only for single words; ties above
  three keys are dropped. A wrong ingredient in the list is worse than no candidate, because "no candidate"
  still has the words and typing.
- **DP-O5 Spelling rules instead of more names.** Skeletons reach languages Janus holds no names for without a
  new data source. They are applied to both sides, so they cannot turn one held name into another.
- **DP-O6 Tabs stay.** The three ways were already tabs; they become equal, icon-bearing tabs with one line of
  claim above. Accessible names are unchanged (other specs' tests and users' habits).
- **DP-O7 The result survives the confirm round trip** (combination products), in memory only.
- **DP-O8 Evaluation on recorded text.** Pixels depend on installed fonts; the recorded text is committed, so the
  matching numbers are exact and cheap to re-check in CI, and the images can be regenerated on request.

## 7. Properties
- **P1** (Req 3.2) Every held name is found (not as `close`) in upper case, lower case, Turkish upper case and
  without marks; arbitrary text gives the same candidates in any letter case. `ingredient-match.test.ts`
- **P2** (Req 3.5) Every `close` candidate's printed word is within `distanceCap` of a held single-word name of
  its key; the cap is 0 below 6 letters and at most 2. `ingredient-match.test.ts`
- **P3** (Req 3.7) Words farther than the cap from every held name, with arbitrary non-letter noise around them,
  give no candidate. `ingredient-match.test.ts`
- **P4** (Req 3.4, 3.8) Salt words are kept in the printed text and never make a candidate next to an
  ingredient; combination labels give each ingredient once. `ingredient-match.test.ts` (examples)
- **P5** (Req 2.3, 2.4, 6.1) No sequence of label actions yields a state with a choice or a request;
  `outboundOf` is `null` unless the state is a finished reading and the choice is valid, and then it is exactly
  the English held name / the NDC / the chosen words. `label-session.test.ts`
- **P6** (Req 3.6) An exact name is never accompanied by a similar one for the same span. `ingredient-match.test.ts`
- **P7** (Req 2.6) `confirmView(r, prefer)` has the same cards and indexes as `confirmView(r)`; only the order
  differs (preferred ingredient first); nothing is chosen. `confirm.test.ts`
- **P8** (Req 4.3) `readLabel` reads upright first, turns only when the upright reading is neither useful nor
  confident, returns the first useful reading, else the most confident. `ocr-passes.test.ts`
- **P9** (Req 5.3) The measured table equals the committed results; after ≥ before in every group; no candidate
  on a label without a held ingredient. `eval/hit-rate.test.ts`
- Rendered checks (Req 1, 2, 4, 7): `e2e/ocr-first.spec.ts`.

## 8. Evaluation (Req 5)
See `evaluation.md` for the method, the numbers and the limits.

## 9. Limits and open items
1. The device list holds the accepted glossary rows (1,126 ingredient keys). An ingredient outside it gives no
   candidate; the words and typing reach the API's full name index. Widening the device list means widening the glossary.
2. The evaluation images are synthetic. Real boxes have glossy foil, curved surfaces, embossing, coloured and
   condensed type, tiny print and several languages at once; none of that is measured here.
3. Only Latin script. Greek, Cyrillic, Arabic and CJK labels are not read (no model is vendored, no names held).
4. The skeleton rules are regularities with exceptions; a name that changes more than its spelling between
   languages (a different national name) is found only if the glossary holds it.
5. A candidate search is one ingredient. A combination product is added as its ingredients, one after the other;
   the list then has one item per ingredient, not one item for the box.
6. The 2,600 px limit and the confidence threshold 75 were chosen on the synthetic set, not tuned on photos.
7. The models stay `tessdata_fast` for the interface language plus English; a label in a third language is read
   with those models.
