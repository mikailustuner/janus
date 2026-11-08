# Wording review: localization (experience, task 22)

**Date:** 2026-11-08
**Reviewer:** localization-reviewer (`.kiro/agents/localization-reviewer.md`), run as a separate read-only agent pass; no files edited by the reviewer.

## Scope and method

- **Files:** `apps/web/messages/{en,tr,de,fr,es}.json`. All namespaces except `Memory`, `Metadata`, `LocaleSwitcher`, `Disclaimer`: 534 keys in each of the five languages. English is the source; tr, de, fr and es are AI drafts.
- **Read against:** `medical-safety.md`, `product.md`, experience `requirements.md` (Req 2, 6, 7, 12–21, Glossary) and `design.md` §7–8. `Memory` and `src/vocabulary/*.json` were read only to compare terms and see how placeholders are filled (`EmergencyNotice.tsx`, `Shell.tsx`).
- **Mechanical checks:** key parity (no key missing in any language); ICU placeholders and plural selectors identical, no empty value; forbidden phrases and reassurance words (`phrases.py`) plus inflected and near forms (Turkish `tanı` occurs only inside longer words; German `setzen … ab` only in the abrupt-stop vocabulary, as a negative); theme words in `.glass` values and in keys without a theme pair (French `Masquer` is a verb and passes the whole-word test); "people" instead of "reports" (no hits); words of 19 or more letters for the 375 px check.
- **Manual check:** every value read side by side in all five languages for meaning, hedges, register and clinical terms.
- **Fixed texts:** the rule-3 no-pattern sentence (`Findings.noPattern`) and `Findings.discuss` are equivalent in all five languages; "Do not stop this medicine suddenly." is in the generated vocabulary in all five; the emergency notice is present everywhere (see TR-1, TR-2, FR-1); "at most 24 months" and "no audit / not a medical device" keep their meaning; no translation adds a compliance or certification claim.

## Summary

| Language | Blocking | Advisory |
|---|---|---|
| EN source (affects all five) | 1 | 1 |
| tr | 3 | 7 |
| de | 0 | 8 |
| fr | 0 | 4 |
| es | 1 | 2 |
| **Total** | **5** | **22** |

**Applied before the stop (2026-11-08):** TR-1 and TR-2 (Turkish emergency lines, case endings): `Emergency.text` is now "Göğüs ağrısı, nefes almada güçlük, inme belirtileri veya ağır alerjik tepki: acil yardım için önce {emergency} arayın." and `Emergency.short` "Acil durumda {emergency} arayın" (the safety audit's A11 asked to keep "first", "önce"). Every other finding waits for the owner's decisions (`wording-review.md`).

## Findings

### EN source (applies to all five languages)

| Key | Issue | Current text (short) | Suggested wording | Severity |
|---|---|---|---|---|
| `Donate.consent.2026-11-v1.check` | The consent checkbox calls the data "anonymous", while the same screen calls it health data stored under GDPR Art. 9(2)(a) and deletable with a token. Anonymous data would fall outside the GDPR, so the claim contradicts the consent it asks for. All four translations copy it. | "…as an anonymous donated report." | "…as a donated report, without my name or contact details." Translate in all four drafts; send to the privacy review. | blocking |
| `Donate.intro`, `Reminder.body` | Same "anonymous" claim outside the consent text. | "…as an anonymous donated report" | "…as a donated report (no name, email or exact date)" | advisory |

### tr

| Key | Issue | Current text (short) | Suggested wording | Severity |
|---|---|---|---|---|
| `Emergency.text` (TR-1) | `{emergency}` is filled from `Memory.emergency.<region>`, which already carries the case ending ("112'yi", "yerel acil durum numaranızı"); the result "önce acil servisi (112'yi) arayın" has two object endings in the most important safety line (rule 10). | "…: önce acil servisi ({emergency}) arayın." | "Göğüs ağrısı, nefes almada güçlük, inme belirtileri veya ağır alerjik tepki: hemen acil yardım için {emergency} arayın." | blocking |
| `Emergency.short` (TR-2) | Same cause; the footer shows "Acil: 112'yi". | "Acil: {emergency}" | "Acil durumda {emergency} arayın" | blocking |
| `MemoryView.*`, `Donate.*`, `Findings.openDetail`, `Findings.memory`, `Settings.statisticsRegion`, `Note.statisticsRegion`, `Research.entries.hypotheses.body`, `Reminder.body`, `Privacy.*` | "Report" is "rapor" in these keys (37 uses) but "bildirim" in the reviewed `Memory` namespace (29 uses); both appear on the same FAERS panel. | "# rapor", "Bağışlanan raporlar" | "bildirim" everywhere, as in `Memory` and TÜFAM usage: "# bildirim", "Bağışlanan bildirimler", "Tüm liste için bildirimler". | blocking |
| `Evidence.status.ok`, `Evidence.noticeType.other`, `Evidence.status.expression_of_concern`, `Evidence.noticeType.expression_of_concern`, `Findings.integrity.expression_of_concern_notice`, `Doctor.title`, `Note.qrAlt` | Once "bildirim" means "report", it must not also mean "notice" or the doctor's answer. | "Bildirim yok", "Endişe bildirimi", "doktor bildirimi" | "Duyuru yok"; "Endişe ifadesi"; "Janus · bir not hakkında yanıt"; "…doktor yanıtı için QR kodu" | advisory |
| `MemoryView.combinationReports`, `MemoryView.scopeSuspect` | "adlandıran/adlandırıldığı" means naming in the sense of giving a name. | "Hepsini adlandıran # rapor" | "Hepsinin geçtiği # bildirim"; "İlacın şüpheli olarak belirtildiği bildirimler" | advisory |
| `MemoryView.ratio`, `MemoryView.ratioLabel` | "odds" is dropped; "Raporlama oranı" reads like PRR. | "Raporlama oranı (ROR)" | "Raporlama olasılık oranı (ROR)" (native clinical review; note: "olasılık" is on the `Memory` causal word list, so the word-list exception would need an owner decision) | advisory |
| `MemoryView.ratio`, `Findings.priority` | The range phrase is incomplete. | "aralık {low} ile {high}" | "aralık: {low} ile {high} arası" | advisory |
| `MemoryView.intro` | "advers olay" is jargon for a caregiver. | "…advers olay raporlarında…" | "…istenmeyen olay bildirimlerinde…" | advisory |
| `Confirm.statusEs.presentation` | "Sunum" reads as a slide presentation. | "Sunum durum kodu…" | "Ambalaj durum kodu {code}, {date} tarihinden beri (…)" | advisory |
| `Home.demo` vs `Demo.title`, `Common.retry` and other buttons | Address mixed ("dene" / "deneyin") in one flow. | "Demoyu dene" / "Demoyu deneyin" | One style for buttons (bare imperative) and "-in" in sentences; at least align `Home.demo` and `Demo.title`. | advisory |

### de

| Key | Issue | Current text (short) | Suggested wording | Severity |
|---|---|---|---|---|
| `Findings.count.glass`, `Findings.groupConfirmed.glass`, `Findings.kind.glass` | "Verschreibungskaskaden" (22 letters) as a 32 px Glass large title is about 390 px wide, over 343 px of content at 375 px. | "Mögliche Verschreibungskaskaden" | A soft hyphen in the value ("Verschreibungs­kaskaden") or rely on `hyphens: auto` (set for `lang=de`); check at 375 px with large text. | advisory |
| `Settings.readAloud` | "Befunde" means clinical findings and leans toward diagnosis; elsewhere "Ergebnisse". | "Befunde vorlesen" | "Ergebnisse vorlesen" | advisory |
| `Home.intro`, `Note.intro` | "deren" does not fit "die Ärztin oder den Arzt". | "…in deren Sprache." | "…in ihrer oder seiner Sprache." | advisory |
| `Demo.patients.ohio.summary` | "Dosen" means tins or cans. | "US-Apothekendosen, gefunden über die NDC." | "Tablettenröhrchen aus US-Apotheken, gefunden über die NDC." | advisory |
| `Privacy.sent.body` | "Startmonaten" here, "Beginnmonate" elsewhere. | "…mit ihren Startmonaten…" | "…mit ihren Beginnmonaten…" | advisory |
| `Doctor.demo` | Does not match the demo label (Req 17.10, `Demo.label`). | "Demo · synthetische Patientendaten." | "Demo · synthetischer Patient. Dieses Formular sendet nichts." | advisory |
| These namespaces vs `Memory` and the vocabulary `abrupt_stop` | "Medikament" (60 uses) vs "Arzneimittel" in `Memory` (18) and the abrupt-stop sentence. | — | One word for the patient UI; if "Medikament", the glossary sentence changes too (glossary decision). | advisory |
| `Research.rule7`, `Research.entries.hypotheses.body`, `Research.entries.validation.body` | "Wiederverwendung" sounds like recycling. | "Ergebnisse zur Wiederverwendung…" | "Ergebnisse zum Drug Repurposing (Arzneimittel-Repositionierung)…" (native review) | advisory |

### fr

| Key | Issue | Current text (short) | Suggested wording | Severity |
|---|---|---|---|---|
| `Emergency.text`, `Emergency.short` (FR-1) | `Memory.emergency` returns "le 112": "appelez d'abord les secours (le 112)", "Urgence : le 112". Understandable but clumsy. | "…appelez d'abord les secours ({emergency})." | "…appelez d'abord les secours en composant {emergency}." / "Urgence : composez {emergency}" | advisory |
| `Settings.deleteBody`, `Demo.neverDonated`, `Donate.intro`, `MemoryView.donatedTitle`, `Reminder.body`, `Privacy.stored.body`, `Privacy.howLong.body` | "donné" is ambiguous ("Les données données", "ne sont jamais données"). | "Les données données…", "signalement donné" | "Les données issues des dons…"; "Les données de démo ne font jamais l'objet d'un don."; "Signalements issus de dons (Janus)" | advisory |
| `Timeline.link`, `Timeline.linkSameMonth`, `Findings.timing.*` | "a été commencé" does not agree with feminine ingredient names. | "{marker} a été commencé … après {index}" | "{marker} : début {months} mois après {index}." | advisory |
| `Doctor.demo` | "fictif" does not match `Demo.label` ("synthétique"). | "Démo · patient fictif." | "Démo · patient synthétique. Ce formulaire n'envoie rien." | advisory |

### es

| Key | Issue | Current text (short) | Suggested wording | Severity |
|---|---|---|---|---|
| `MemoryView.*`, `Donate.*`, `Findings.openDetail`, `Findings.memory`, `Settings.statisticsRegion`, `Note.statisticsRegion`, `Shell.donate`, `Reminder.body`, `Privacy.*` | "Report" is "notificación" here (35 uses) but "informe" in the reviewed `Memory` namespace (26 uses); both on the same panel. | "# notificaciones" | One term: "notificación" (AEMPS pharmacovigilance usage, reopens `Memory`) or "informe" here. Owner decides; both namespaces must match before launch. | blocking |
| `Confirm.regionNotSupported` | Req 12.5 needs "not supported yet"; "no está disponible" reads like the 503 message that Req 12.6 keeps separate. | "Esta región todavía no está disponible." | "Janus todavía no admite esta región." | advisory |
| `Doctor.demo` | "ficticio" does not match `Demo.label` ("sintético"). | "Demo · paciente ficticio." | "Demo · paciente sintético. Este formulario no envía nada." | advisory |

### Checked with no findings

- Forbidden phrases: none in any language, including inflected forms.
- False reassurance: no reassurance words; `=0` texts never stand without the rule-3 sentence.
- Glass vocabulary: no `.glass` value and no key without a theme pair contains a theme-device word in any language.
- Hedges and meaning: "pattern, not verdict" and the discuss hedge equivalent everywhere; `Research.rule7` keeps "not treatments" (Turkish "tedavi değildir" is not the forbidden "tedavi eder"); Privacy keeps "not formal differential privacy", "no outside body has audited", "not a HIPAA covered entity", "at most 24 months", tokens 28–35 days.
- Consistent terms: prescribing cascade; deletion token; outcome loop; ingredient (etkin madde / Wirkstoff / substance active / principio activo); range (aralık / Bereich / intervalle / intervalo); formal address in de, fr, es.

## Terms needing a native-speaker clinical review before launch

- **tr:** "reçete kaskadı" vs "reçeteleme kaskadı"; "bildirim" vs "rapor"; "Raporlama olasılık oranı (ROR)"; "Endişe ifadesi"; "yeniden kullanım" vs "yeniden konumlandırma"; "Ambalaj durum kodu".
- **de:** "Expression of Concern" and "Reporting Odds Ratio" kept in English; "Verschreibungskaskade"; repurposing term; "Medikament" vs "Arzneimittel".
- **fr:** "cascade de prescription" vs "cascade médicamenteuse"; "rapport de cotes de signalement"; "signalement issu d'un don"; "boucle de retour".
- **es:** "notificación" vs "informe"; "razón de odds de notificación"; "cascada de prescripción"; "circuito de resultados".
- **All:** the doctor-facing wording of the outcome questions and the note text comes from the API (glossary) and needs its own native clinical read in each doctor language.
