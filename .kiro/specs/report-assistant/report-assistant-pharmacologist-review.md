# Report Assistant review: pharmacologist

**Date:** 2026-11-09
**Reviewer:** pharmacologist (`.kiro/agents/pharmacologist.md`), run as a separate labelled pass by the implementing
agent, in that role only. Scope: which medicine is the suspect, how ingredients and events are named, the field
mappings in `apps/web/src/report/mapping.ts` against `data/report_channels.csv`, and the MedDRA decision (DP3).

## What holds

- **Suspect medicine from a finding** = the finding's index (first) medicine, drug A of the cascade, whose adverse
  event the cascade describes. The marker medicine (drug B, started for the event) is not called suspect; it is among
  the other medicines, ticked by default, and can be unticked. This matches the PIPC pattern.
- **Names:** the box name as the person entered it, plus the ingredient name by the note's rule (doctor-loop DP16);
  combination products list every ingredient. In the doctor view there is no box name, so the medicine is the
  ingredient name (editable). No ATC code goes into the draft.
- **Event:** the Janus lay label of the event key (`memory_events.csv` `label_*`, Janus wording accepted by the owner
  on 2026-11-08) or the person's own words. The PT column of that file is not shipped to the client (the generated
  vocabulary has no PT field); nothing in the draft is a MedDRA code.
- **Onset** is left to the person ("don't know" by default): the marker medicine's start month is not the onset of
  the event and is not used as one.
- **No advice:** the draft does not fill the forms' "action taken" / "stopped because of it?" questions; nothing
  suggests changing a medicine.
- **Mappings:** each mapped label is the form's own question for that value (TÜFAM e-form `Reaksiyon/belirti`, the
  reaction section's `Başlangıç tarihi`, `Sonuç`, `İlaç adı`; TÜFAM patient form sections 2 and 3; 3500B A3, A4, C1,
  E11; BfArM PDF; ANSM Cerfa; NotificaRAM tabs 2–4; EMA "What to report" headings). A test checks every label is in
  the recorded field list, in form order.

## Findings

| id | Severity | Finding | Done |
|----|----------|---------|------|
| F1 | advisory | 3500B E11 asks for **prescription** medicines and devices; over-the-counter medicines and supplements belong in E10. Janus does not know which list items are prescription-only, so all ticked medicines go under E11. | Open: documented here and on the pre-launch checklist; the person can move values. |
| F2 | advisory | TÜFAM `İlaç adı` asks for the full name as on the box; Janus writes "Box name (ingredient)". | Kept: the ingredient helps the authority match the product, the value is editable, and the TÜFAM minimum is "one suspect medicine". |
| F3 | advisory | Some lay labels carry a clinical word in brackets that is also a MedDRA PT (e.g. "Muscle pain or inflammation (myalgia, myositis)"). These are ordinary medical words inside Janus's own label, not MedDRA content or codes. | No change; DP3 holds; the MSSO terms check stays on the checklist. |
| F4 | advisory | The TÜFAM outcome options include "Ölüm" / "Öldü" (death). They are the form's own options, needed when a relative reports; "Not answered" is preselected. | Kept as the form's wording, with translations. |
| F5 | advisory | The 3500B has no patient outcome question; the outcome stays under the Janus label instead of a guessed field (A2 is seriousness). | Agreed (DP6). |

## Verdict

Pass. No blocking finding; F1 and F2 are documented limitations of a draft the person reviews and edits.
