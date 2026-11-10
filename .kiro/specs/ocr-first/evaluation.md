# Evaluation: ingredient names from label images (ocr-first Req 5)

> Measured 2026-11-10 on the dev machine. **The images are synthetic: text rendered by a browser. They are not
> photos of real boxes, and these numbers say nothing certain about real photos.**

## Method
1. `node apps/web/scripts/ocr-eval-fixtures.mjs` draws 366 label-like images with headless Chromium from a seeded
   case list (nothing is downloaded; brand names are invented words). Each label has a brand line with a strength,
   the ingredient line (with a salt where the ingredient usually has one), a form line, a count line and a storage
   sentence in the label's language; every second label repeats the ingredient in a "contains" line.
   - 247 labels with one ingredient in a language Janus holds its name for (50 ingredients × en, tr, de, fr, es
     where the glossary has the name);
   - 75 labels in a language Janus holds no names for (15 ingredients × Italian, Portuguese, Dutch, Polish, Latin;
     names written from general knowledge as test inputs);
   - 20 combination labels (two or three ingredients);
   - 24 labels without a held ingredient (16 with a brand only, 8 with an ingredient outside the device list).
   - Varied per label: 7 fonts (DejaVu Sans, Serif, Condensed, Mono; Lato; C059; FreeSans), ingredient text of
     13 / 18 / 26 CSS px rendered at 2×, rotation 0° / 2° / −4° / 7° / 90° / 270° / 180°, as printed / upper case /
     title case, and nine looks: plain, inverse (white on navy), coloured band, low-contrast grey, blur, a slanted
     box face (perspective), noise, strong JPEG compression, half resolution.
   - Read with the interface language of the label two times out of three and with another one otherwise; the
     other-language labels are read with the English model only.
2. `OCR_EVAL=1 pnpm vitest --run src/scan/eval/ocr-run.test.ts` reads every image with the app's recogniser
   (tesseract.js 7.0.0, `tessdata_fast`, the same options) and writes the text of each reading to
   `apps/web/src/scan/eval/ocr-text.json` (committed; the images are not, because pixels depend on the fonts
   installed).
3. `pnpm vitest --run src/scan/eval/hit-rate.test.ts` computes the table from the recorded text and fails if it
   differs from `results.json`, if "after" is below "before" anywhere, or if a label without a held ingredient gets
   a candidate.

**Before** = what the app could do before this spec if it had offered candidates: one reading of the photo as
taken, and a printed word or phrase that equals a held name apart from letter case. (The app before this spec
offered no candidates at all: the user picked the words by hand. This baseline is the plainest automatic matcher,
not a measurement of the old screen.)
**After** = the reading rule of Req 4.3 (deskew; turned readings when the upright one names nothing and is not
confident) and `matchIngredients`.
**Hit** = every expected ingredient is among the candidates. **Wrong candidate** = the number of labels with at
least one candidate that is not an expected ingredient.

## Result
| Group | Labels | Hit before | Hit after | Wrong candidate before | after |
|---|---:|---:|---:|---:|---:|
| all labels that name a held ingredient | 342 | 173 (50.6 %) | 342 (100.0 %) | 0 | 0 |
| held languages (en, tr, de, fr, es), one ingredient | 247 | 141 (57.1 %) | 247 (100.0 %) | 0 | 0 |
| &nbsp;&nbsp;label in en | 50 | 31 (62.0 %) | 50 (100.0 %) | 0 | 0 |
| &nbsp;&nbsp;label in tr | 49 | 27 (55.1 %) | 49 (100.0 %) | 0 | 0 |
| &nbsp;&nbsp;label in de | 50 | 19 (38.0 %) | 50 (100.0 %) | 0 | 0 |
| &nbsp;&nbsp;label in fr | 49 | 30 (61.2 %) | 49 (100.0 %) | 0 | 0 |
| &nbsp;&nbsp;label in es | 49 | 34 (69.4 %) | 49 (100.0 %) | 0 | 0 |
| other languages (it, pt, nl, pl, Latin), one ingredient | 75 | 24 (32.0 %) | 75 (100.0 %) | 0 | 0 |
| combination labels (every ingredient found) | 20 | 8 (40.0 %) | 20 (100.0 %) | 0 | 0 |
| upright or slightly tilted (0°, 2°, −4°, 7°) | 210 | 173 (82.4 %) | 210 (100.0 %) | 0 | 0 |
| on its side or upside down (90°, 270°, 180°) | 132 | 0 (0.0 %) | 132 (100.0 %) | 0 | 0 |
| ingredient text 13 px (image at 2×) | 107 | 62 (57.9 %) | 107 (100.0 %) | 0 | 0 |
| ingredient text 18 px (image at 2×) | 129 | 59 (45.7 %) | 129 (100.0 %) | 0 | 0 |
| ingredient text 26 px (image at 2×) | 106 | 52 (49.1 %) | 106 (100.0 %) | 0 | 0 |
| look: plain | 71 | 40 (56.3 %) | 71 (100.0 %) | 0 | 0 |
| look: inverse | 32 | 13 (40.6 %) | 32 (100.0 %) | 0 | 0 |
| look: band | 33 | 18 (54.5 %) | 33 (100.0 %) | 0 | 0 |
| look: grey | 34 | 17 (50.0 %) | 34 (100.0 %) | 0 | 0 |
| look: blur | 30 | 11 (36.7 %) | 30 (100.0 %) | 0 | 0 |
| look: perspective | 38 | 19 (50.0 %) | 38 (100.0 %) | 0 | 0 |
| look: noise | 38 | 25 (65.8 %) | 38 (100.0 %) | 0 | 0 |
| look: jpeg | 35 | 15 (42.9 %) | 35 (100.0 %) | 0 | 0 |
| look: lowres | 31 | 15 (48.4 %) | 31 (100.0 %) | 0 | 0 |
| no held ingredient on the label (a candidate here is wrong) | 24 | – | – | 0 | 0 |

In all 342 labels the first candidate after is an expected ingredient.

## How to read it
- **Two separate gains.** Among labels photographed upright the gain is from matching: 82.4 % → 100 % (salt words
  written as one word with the name, diacritics, names of other languages, misread letters). Labels on their side or
  upside down could not be read before at all (0 %) and are read after by the turned readings. The overall 50.6 %
  depends on the share of turned labels in this set (39 %), which was chosen, not observed.
- **The set is saturated.** 100 % means these images are too easy to show where the method fails, not that it does
  not fail. Rendered text has sharp edges, even light, flat paper and one text block; the nine looks only hint at
  a photo.
- **The set is not held out.** Three misses seen in earlier recordings of this same set led to changes (a name
  split in two by the recogniser; scraps of a badly read photo adding up to a short name). The numbers above are
  after those changes.
- **A text-only check on names not used to write the spelling rules** (`ingredient-match.test.ts`, no images):
  15 ingredient names each in Czech, Romanian, Hungarian, Swedish and Lithuanian give 15, 15, 15, 15 and 14 of 15,
  and no wrong ingredient. The Lithuanian miss is an ending (`-is`) outside the rules on a short name.

## Limits
- Not measured: real boxes (foil, curved or embossed surfaces, coloured or condensed type, very small print,
  several languages on one face, glare, motion blur, a finger over the text), pharmacy labels, handwriting.
- Not covered: non-Latin scripts; ingredients outside the device list (1,126 keys; they give no candidate by
  design and are reached by tapping words or typing); names that differ between countries by more than spelling.
- The label layout is one template. A real box face with long marketing or legal text has more words that could
  be close to an ingredient name; the wrong-candidate count of 0 on 366 simple labels is not a rate for real boxes.
- Fonts are those installed on the dev machine; another machine renders other pixels (the recorded text makes the
  matching numbers reproducible, not the recognition).
- Timing was not measured on a phone.
