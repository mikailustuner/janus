# Contributing corrections

Janus depends on open data that other people maintain. While building it we found errors in some of those
sources. We fixed them **inside Janus** (each fix is a reviewed row with its evidence) and list them here so that
anyone can report them **upstream**, where the fix helps everyone. Janus has not submitted any of these reports
itself.

If you find an error in Janus's own files (`data/`, the cascade data package, a translation, a rule mapping),
open an issue or a pull request on the Janus repository with the row, what is wrong and the evidence (a WHOCC
page, a label, a paper). Medical content is changed only after review; nothing is changed on the strength of a
single unsourced comment.

## 1. Wikidata: wrong ATC codes on ingredient items

Source of the fix: `data/atc_code_exclusions.csv` (rows with `source = wikidata`), review
`.kiro/specs/drug-resolution/atc-code-review.md`. Each code was checked by hand on the WHOCC ATC/DDD index group
page (index last updated 2026-01-20) on 2026-11-08.

| Wikidata item | ATC code on the item (P267) | What the code actually is (WHOCC) | Suggested correction |
|---|---|---|---|
| [Q7226181](https://www.wikidata.org/wiki/Q7226181) polycarbophil calcium | A06AC07 | wheat fibre (triticum); polycarbophil calcium is A06AC08 | remove A06AC07 (keep A06AC08) |
| [Q16252338](https://www.wikidata.org/wiki/Q16252338) insulin degludec | A10AD06 | the combination insulin degludec + insulin aspart | remove A10AD06 from the single-insulin item (keep A10AE06) |
| [Q422241](https://www.wikidata.org/wiki/Q422241) sodium lauryl sulfate | A06AD13 | sodium sulfate, a saline laxative | remove A06AD13 (the item is a detergent excipient) |
| [Q419020](https://www.wikidata.org/wiki/Q419020) JWH-018 | N02BG10 | the class code for cannabinoids (medicinal cannabis) | remove N02BG10 from the synthetic research chemical |
| [Q22075864](https://www.wikidata.org/wiki/Q22075864) ferric citrate (item) | B03AB06 | not in the current index | remove, or mark deprecated with an end date and a reference to the WHOCC page |

**How to report:** these are statements anyone can edit. Sign in to Wikidata, open the item, and either deprecate
the statement (rank "deprecated", reason for deprecated rank: "incorrect value") with a reference URL to the
WHOCC group page (`https://atcddd.fhi.no/atc_ddd_index/?code=<group>&showdescription=no`) and the retrieval date,
or remove it and explain why on the item's talk page. For several items at once, post the list on
[WikiProject Medicine](https://www.wikidata.org/wiki/Wikidata:WikiProject_Medicine). Quote the code and the WHOCC
group only; the WHOCC index text itself must not be copied.

## 2. TİTCK: ATC codes published on single-ingredient products

Source of the fix: `data/atc_code_exclusions.csv` (rows with `source = titck`). In the TİTCK licensed human
medicines list (weekly, checked 2026-11-06/07) a single-ingredient product of each of these ingredients carries
another substance's ATC code. Janus keeps the code on the product as published but does not let it become the
ingredient's code. Janus does not republish TİTCK data; find the products by searching the current TİTCK list for
the ingredient and the code below.

| Ingredient (Wikidata) | Code published on the product | What the code is (WHOCC) | Expected group |
|---|---|---|---|
| ketoconazole (Q407883) | M01AE03 | ketoprofen | antifungal (D01AC, G01AF, J02AB, H02CA) |
| mefenamic acid (Q284321) | N02AX02 | tramadol | M01AG |
| esomeprazole (Q553223) | N03AX16 | former code of pregabalin, no longer in the index | A02BC05 |
| levocetirizine (Q421091) | R06AB04 | chlorphenamine | R06AE09 |
| prednisolone (Q11426176) | D07AB08 | desonide | prednisolone's own codes |
| econazole (Q417141) | D01AC04 | chlormidazole | D01AC03, G01AF05 |
| lidocaine (Q216935) | R02AA05 | chlorhexidine | lidocaine's own codes |

**How to report:** to TİTCK (Türkiye İlaç ve Tıbbi Cihaz Kurumu), the agency that publishes the list, through
its official contact channels on [titck.gov.tr](https://www.titck.gov.tr) or a written request through
[CİMER](https://www.cimer.gov.tr). Name the list and its date, the barcode of the product as it appears in the
list, the code and the WHOCC group page. The marketing authorisation holder of each product can also correct its
own entry. Check the current list first: TİTCK may already have corrected it.

## 3. Others

- **TİTCK/Wikidata disagreements.** 93 ingredient-code pairs share no level-4 ATC group between TİTCK and Wikidata
  (`atc-code-review.md`); only the twelve above were confirmed as errors. The others need a pharmacist before any
  report.
- **WHOCC.** Janus found no error in the WHOCC index itself. Questions about a code go to the WHO Collaborating
  Centre for Drug Statistics Methodology ([atcddd.fhi.no](https://atcddd.fhi.no/)).
- **PIPC list.** Janus uses Table 1 as published (Rochon et al., Eur Geriatr Med 2025). Questions about a row go to
  the authors through the journal.

Before sending any report, re-check the source: data on all of these sites change weekly or quarterly.
