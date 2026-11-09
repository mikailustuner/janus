# Review: card design, `Cards` namespace (localization-reviewer, Req 29)

**Pass:** `localization-reviewer` (`.kiro/agents/localization-reviewer.md`), one read-only agent pass on the `Cards` block of
`apps/web/messages/{en,tr,de,fr,es}.json` (2026-11-09), with the screens where each key is used. Moved sentences keep
their existing, already reviewed keys.

## Findings: 1 blocking, 11 advisory

| Key | Lang | Finding | Severity | Applied |
|---|---|---|---|---|
| `memory.janus` + the 4-segment filter | all | Four segments at 375 px leave about 80 px each; long labels broke mid-word | blocking (layout) | Segmented control is now a responsive grid (2 × 2 on phones, one row from about 720 px), words break only between words; ES shortened to "Notificado vía Janus"; screenshot checked |
| `memory.together` | all | "Together" alone does not say what is together | advisory | "Medicines together" / "İlaçlar birlikte" / "Medikamente zusammen" / "Médicaments ensemble" / "Medicamentos juntos" |
| `memory.janus` | tr | Participle without a noun | advisory | "Janus üzerinden bildirilenler" |
| `label.casesTop` | tr | Comma breaks the phrase | advisory | "{cases} vakadan ilk {k} içinde" |
| `label.checkedByDoi` | tr | "9 / DOI ile kontrol edildi" can read as "9 DOIs" | advisory | "tanesi DOI ile kontrol edildi" (as `Evidence.line.sources`) |
| `label.sources` | tr | "12 toplam kaynak" vs natural "toplam 12 kaynak" | advisory | Kept (reads correctly under a large figure); native check |
| `passport.listed` | tr | "listede" terse | advisory | "… tanesinde listede yer alıyor" (as `Passport.presentNote`) |
| `passport.listed` | all | "Listed in 1 of 4 countries" could be read as "on sale" | advisory | See the safety review: `Passport.presentNote` stays on the screen with the rows |
| `label.reports` | fr | Light namespace uses "déclarations FAERS", Cards "signalement" | advisory, out of scope | Cards keeps the canonical "signalement"; Light wording left for a separate change |
| `label.cards` | fr | Séance uses "Affection", Light "état" | advisory, out of scope | No change |
| `memory.all` | fr, es | "Tous"/"Todos" may read better | advisory | Native speaker to decide |
| `label.witnesses` | tr | "tanıktan" contains the substring "tanı" | advisory | The forbidden-phrase test matches whole words (catalogue tests green); `Seance.count` already uses "tanık" |

## Checked and clean
Forbidden phrases (inflected forms included), one word per term (report: bildirim / Meldung / signalement / notificación;
active ingredient, pattern, card, condition, witness, box), counts always "reports", formal register, plural forms
(TR one = other, FR `one` covers 0, FR/ES feminine agreement, DE dative), Turkish word order under a large figure,
German and French label lengths (tiles allow two-line labels).

## Verdict
Approved after the blocking layout fix (applied and checked on the 375 px screenshot). Native-speaker review still
needed before launch for the TR tile labels (`sources`, `checkedByDoi`, `casesTop`, `passport.listed`), FR "Tout/Tous",
ES "Todo/Todos", DE "Zustand" (used across Light and Séance).
