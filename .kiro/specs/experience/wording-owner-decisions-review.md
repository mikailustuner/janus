# Wording review of the owner decisions (experience, task 23)

**Date:** 2026-11-08
**Passes:** localization-reviewer and safety-auditor (`.kiro/agents`), run as two separate read-only agent passes on every
row changed for the owner's decisions of `wording-review.md` (web catalogues, note glossary, `memory_events.csv`) and on
the whole `Home` namespace and home page. No file was edited by the reviewers; the fixes below were applied afterwards.

## Localization pass: 5 blocking, 7 advisory

| Key | Lang | Finding | Applied |
|---|---|---|---|
| `Memory.codes.regions_not_comparable` | es | Last sentence lost in the informe → notificación pass | Restored ("Cada región se compara solo con las demás notificaciones de la misma región.") — blocking, fixed |
| `Evidence.line.byStatus` | tr | "bildirim" still meant a notice | "Duyuru yok … endişe ifadesi …" — blocking, fixed |
| glossary `integrity.by_status`, `finding.notice.expression_of_concern` | tr | Same in the note | "duyuru yok", "endişe ifadesi" — blocking, fixed |
| `Note.qrTitle`, glossary `outcome_loop.heading`, `outcome.heading`, `outcome.stored_fields` | tr | The doctor's answer still called "bildirim" | "yanıt" throughout — blocking, fixed |
| glossary `outcome.heading` | es | "Informe del resultado" | "Respuesta sobre el resultado"; "la semana de la respuesta" — blocking, fixed |
| `MemoryView.ratio`, `.ratioLabel` | tr | Two words for ROR (web "odds", note "olasılık") | "Bildirim olasılık oranı (ROR)" in both — fixed |
| `OutcomeConsent.2026-11-v2.stored` | tr | "olayın" lacked the possessive | "olayının" — fixed |
| `MemoryView.outcomesTitle` | tr | "bildirilen" for doctor answers | "Doktor notları üzerinden gelen sonuçlar (doğrulanmamış)" — fixed |
| `MemoryView.outcomesTitle` | de | "Ergebnisse" now means findings and outcomes | "Über Arztnotizen gemeldete Behandlungsverläufe (nicht überprüft)" — fixed |
| `Home.how3` | de | "in deren Sprache" | "in ihrer oder seiner Sprache" — fixed |
| `Home.demoHint` | tr | Clumsy relative clause | "Kayıt gerekmez. Üç sentetik hasta; ürün adları uydurmadır." — fixed |
| `Home.resume` | tr | Register mix with the buttons | Left for the native-speaker review (pre-launch) |

Checked with no finding: placeholders and plurals identical (601 keys in each language); no forbidden or reassurance
phrase; "anonymous" gone everywhere; Spanish gender agreement; Turkish case endings after rapor → bildirim; country names;
status chips equal to the note rows; role wording; consent v2 meaning; the decision-7 batch; formal register; Glass values.

## Safety audit: 1 blocking, 8 advisory

| # | Finding | Applied |
|---|---|---|
| 1 | "Order not confirmed" was keyed to the engine status `possible`, which also covers a known order after the window (the card then showed "A, then B" next to "Order not confirmed"). | Label chosen from the timing: within window "Order fits the pattern", after the window "Order fits, later than the usual window" (new, owner to confirm the words), same month / unknown "Order not confirmed"; app and note (doctor-loop DP41) — blocking, fixed |
| 2 | `Home.privacyLine` said the medicine list stays on the device, while ids and start months are sent | "Photos of the boxes stay on this device. Janus has no account, does not store your medicine list and sends only the codes the check needs." — fixed |
| 3 | Consent v2 "only" left out the direction and the product confirmation | Both added in five languages — fixed |
| 4 | Doctor-facing `outcome.stored_fields` did not name the rule | Added in five languages — fixed |
| 5 | Web priority sentence said "range" for a confidence interval | "confidence interval" in five languages — fixed |
| 6 | "Janus checks 65 patterns" while 63 are checkable | "compares your medicines with 65 published … patterns" — fixed |
| 7 | Deduplication limit folded | `deduplicated_by_case_version_only` shown without expanding — fixed |
| 8 | `product.md` still said "doctor-confirmed outcomes" | Aligned — fixed |
| 9 | "First medicine … Second" could read as a time order | Accepted as is ("of the pattern", as on the doctor form) |

Also fixed: no empty "details" section when every caveat is visible; the print blob URL is revoked; `.env.example`
names both consent versions. Could not check (pre-launch): rendered PDF order on real devices, deployed consent lists,
native fluency.
