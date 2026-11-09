# Zombie Alert review: localization-reviewer

**Date:** 2026-11-09
**Reviewer:** localization-reviewer (`.kiro/agents/localization-reviewer.md`), run as a separate read-only agent pass
against `medical-safety.md`, `product.md` and `design.md`. The reviewer edited no files. English is the source; tr, de,
fr and es are AI drafts.

## Scope and method

- The `ZombieAlert` namespace in `apps/web/messages/{en,tr,de,fr,es}.json`, read with `components/zombie/Zombie.tsx`
  and the spec.
- Forbidden phrases and reassurance words, with inflected forms: no hits. Theme words: only `title.twoFaces` says
  zombie (allowed); `title.glass` and every shared key are clean. `notification` names no medicine, PT or event.
  `{doi}` intact everywhere.
- Terms compared with the rest of each file: retracted, evidence, doctor note, notice, dismiss, formal address.

## Summary

| Language | Blocking | Advisory |
| -------- | -------- | -------- |
| EN       | 0        | 1        |
| TR       | 0        | 2        |
| DE       | 0        | 1        |
| FR       | 0        | 3        |
| ES       | 1        | 2        |

## Findings and what was done

| #   | Key, language                | Finding                                                                                               | Done                                                                                        |
| --- | ---------------------------- | ----------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| 1   | `notify*`, ES (**blocking**) | "aviso" already means a publication notice in this file (`Evidence.status.ok` "Sin aviso", `notice`)  | **Fixed:** the OS notification is "alerta" (as `noChange` already says).                    |
| 2   | `noChange`, EN               | Second sentence stiff; the proposed "If you have questions…" contains the forbidden phrase "you have" | Kept "Questions about your medicines are for your doctor or pharmacist."                    |
| 3   | `noChange`, TR               | "bir ilacı değiştirmek" reads as swapping a drug                                                      | **Fixed:** "ilaçlarınızda bir değişiklik yapmak".                                           |
| 4   | `notify*`, TR                | "uyarı" avoids "bildirim" (report) and "duyuru" (notice) but also means label warnings                | Kept; native clinical review on the pre-launch checklist.                                   |
| 5   | `simulate`, TR               | Awkward noun phrase                                                                                   | **Fixed:** "Bir kaynağın geri çekilmesini canlandır (demo)".                                |
| 6   | `noChange`, DE               | "Hinweis" = publication notice; "ein Medikament ändern" not idiomatic                                 | **Fixed:** "Diese Mitteilung allein ist kein Grund, etwas an Ihren Medikamenten zu ändern." |
| 7   | `noChange`, FR               | "suffire pour", "modifier un médicament"                                                              | **Fixed:** "…n'est pas une raison de changer quoi que ce soit à vos médicaments."           |
| 8   | `removed`, `changed`, FR     | Headings over a list of phrases need feminine plural                                                  | **Fixed:** "Phrases retirées" / "Phrases modifiées".                                        |
| 9   | `changesIntro`, FR           | "de nouveau" placement                                                                                | **Fixed:** "à nouveau".                                                                     |
| 10  | `title.glass`, FR            | 82 characters wrap to four lines at 375 px                                                            | **Fixed:** "Mise à jour : une source de votre note pour le médecin a été rétractée".        |
| 11  | `removed`, `changed`, ES     | Plural over `frases`                                                                                  | **Fixed:** "Eliminadas" / "Cambiadas".                                                      |
| 12  | `noChange`, ES               | "cambiar un medicamento" narrower than EN                                                             | **Fixed:** "hacer cambios en sus medicamentos".                                             |

Keys added after this pass for the safety audit (`simulatedTitle`, `simulatedStamp`, `notificationDemo`, `passOn`, new
`notification`) follow the same terms (TR canlandırma/uyarı, ES alerta, DE Arztnotiz, FR note pour le médecin) and pass
the forbidden-phrase, reassurance and theme-word tests.

**Verdict:** changes requested → applied. Native clinical review before launch (TR "uyarı", ES "retractarse", which can
also mean "to recant").
