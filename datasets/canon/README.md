# Janus Canon data package (séance, past witness)

Derived data from Ibn Sina's *al-Qanun fi al-Tibb*, Book 2 (*al-Adwiya al-mufrada*, simple
drugs), for the Janus séance. Research prototype, not a medical device. Nothing here is medical
advice; historical uses are hypotheses for research, not treatments.

## Licence and attribution

This package is licensed under **CC BY-NC-SA 4.0** (full text in `LICENSE`), the licence of its
source. It is separate from the Janus source code, which is Apache-2.0; the Apache licence does
not apply to the files in this directory.

Source: OpenITI, `0428IbnSina.QanunFiTibb.Shamela0010706-ara1` (primary version), repository
[OpenITI/0450AH](https://github.com/OpenITI/0450AH), commit
`81d1d9e0f0af42a822f0136fe4f49776471ef702` (2025-11-27), git blob
`de2e584560c19a18c0dca75edb435c673c69fcb9`. Licence record: OpenITI release 2025.1.9,
[doi:10.5281/zenodo.17767721](https://doi.org/10.5281/zenodo.17767721) (CC BY-NC-SA 4.0).
Please cite: Nigst L, Romanov M, Savant SB, Seydi M, Verkinderen P et al. *OpenITI: a
Machine-Readable Corpus of Islamicate Texts*, version 2025.1.9, Zenodo, 2025.

OpenITI flags this version for `MANY_TYPOS, PAGINATION, MISSING_PARTS`. Some passages are
incomplete, some page numbers are misplaced. Every row keeps a locator to the exact source lines
so a reader can check the passage against an edition.

**Changes made** (CC BY-NC-SA §3(a)(1)(B)): the text was split at its headings; inline section
labels, page markers and milestones were parsed; short clauses that mention wounds, burns,
ulcers or putrefaction were cut out; English summaries and machine translations were added.

## Files

| File | What it is | Made by |
|---|---|---|
| `entries.csv` | one row per Book 2 heading (844): id, level, heading, parent, source lines, printed page | `janus-pipelines run canon` |
| `theme_spans.csv` | clauses with a theme term (534 in 299 entries), the Arabic text, and deterministic rule tags | `janus-pipelines run canon` |
| `source.json` | pinned version, hashes, run id | `janus-pipelines run canon` |
| `reader_ai.csv` | the reader step on a 43-clause sample: substance, conditions, use, English machine translation | AI reader (see below) |
| `identifications.csv` | the 31 substances of the sample: identification, PMC3941892 gold row, Hamdard 1998 entry | Janus (AI-drafted) |
| `review_historian.csv` | historian review pass (AI), one verdict per clause | historian agent (AI) |
| `review_pharmacologist.csv`, `review_pharmacologist_identifications.csv` | pharmacologist review pass (AI) | pharmacologist agent (AI) |
| `claims.csv`, `substances.csv`, `quality.json` | assembled claims, final identifications, extraction quality | `python -m janus_pipelines.jobs.canon_package` |

## Provenance of the reading and the reviews

- **Reader.** No Anthropic API key was configured on 2026-11-08, so the reader step was done
  offline by Claude (model `claude-opus-5-5`, in a Claude Code session acting as the Janus reader
  agent): it read each Arabic clause and the rule tags and wrote the structured fields and an
  English **machine translation**. It is an AI artifact, not a scholarly translation.
- **Reviews.** Two independent AI passes, each run as its own agent: the historian (text,
  translation fidelity, scope) and the pharmacologist (identity, hazards, modern condition
  category, treatment-claim wording). Neither saw the other's file.
- **Status.** Every claim is `ai_review = passed_both`, `expert_review = pending`. No row is
  `reviewed` by a human yet; the experts' review is a pre-launch item.
- **Identifications.** Gold table: PMC3941892 (Aliasl and Khoshzaban 2013, CC BY 3.0), name
  columns only, in `data/canon_gold_pmc3941892.csv`. Hamdard 1998 (© Jamia Hamdard) is **cited
  only**: a row names its letter chapter, entry number and the page of the PDF, never its text.
  An identification is `matches_gold` only when it agrees with the gold row; otherwise it is
  `uncertain` or `not_in_gold`, and the séance screen shows it as uncertain.

## Ottoman samples

None are included. The candidate sources (Sabuncuoğlu's *Mücerrebnâme* and *Terceme-i
Akrabâdîn* theses, the TTK edition of *Cerrâhiyyetü'l-Hâniyye*) could not be read with page-level
citations in this phase (thesis full texts closed or behind a captcha, editions not online), so no
quotation could be verified. Janus does not claim to have mined Ottoman manuscripts.
