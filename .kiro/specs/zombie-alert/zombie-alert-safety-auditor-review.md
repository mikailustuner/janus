# Zombie Alert review: safety-auditor

**Date:** 2026-11-09
**Reviewer:** safety-auditor (`.kiro/agents/safety-auditor.md`), run as a separate read-only agent pass against
`medical-safety.md`, `privacy.md`, `design.md` and `product.md`. The reviewer edited no files.

## Scope

Spec (requirements, design DP1–DP10), `flow/zombie.ts`, `flow/useZombie.ts`, `store/zombie.ts`,
`components/zombie/Zombie.tsx`, `demo/zombie.ts` and its fixture, the `notificationclick` handler in `public/sw.js`,
the additive lines in NotePage, Home, Results, Settings, Shell and `store/hooks.ts`, and the `ZombieAlert` texts.

## What holds

No advice to start, stop or change a medicine; no false reassurance. The emergency notice stays first on home,
results and note; the disclaimer is unchanged. Red only on the "Retracted" label and its icon. The notification text
takes no value. The routine check sends only a date. Demo mode makes no network request. "Delete everything" removes
`janus.v1.zombie`.

## Findings and what was done

| id  | Severity     | Finding                                                                                                                      | Done                                                                                                                                                    |
| --- | ------------ | ---------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| A1  | **blocking** | Demo: heading and red stamp next to a real paper's title before the "simulated" line; a crop shows a real paper as retracted | **Fixed:** the "Simulated in the demo…" line comes first; heading "Simulation: …" (`simulatedTitle`); label "Retracted (simulated)" (`simulatedStamp`). |
| A2  | **blocking** | The demo notification used the real text                                                                                     | **Fixed:** `notificationDemo` ("Demo simulation: no source was really retracted…").                                                                     |
| A3  | **blocking** | Settings says the check sends "only a date", but the truncation fallback sent the cited ids                                  | **Fixed:** fallback removed; a possibly truncated answer moves `since` to its oldest date (Req 2.5, P5, unit test).                                     |
| A4  | advisory     | The Settings switch wrote `janus.v1.zombie` in demo mode                                                                     | **Fixed:** in demo the opt-in lives in the memory document; e2e asserts no local-storage key after the demo notification.                               |
| A5  | advisory     | "Open Janus to see the updated note" is not accurate                                                                         | **Fixed:** "Open Janus to update the note." (5 locales).                                                                                                |
| A6  | advisory     | The first check sent the exact date the note was made                                                                        | **Fixed:** the first `since` is seven days before the note.                                                                                             |
| A7  | advisory     | Nothing tells the patient to pass the new note to a doctor who has the old one                                               | **Fixed:** `passOn` line in "What changed".                                                                                                             |
| A8  | advisory     | "Hide this" closes the alert for good                                                                                        | Accepted (any later note is built without the source); recorded in design §8.                                                                           |
| A9  | advisory     | Demo integrity counts stay as recorded after the simulation                                                                  | Recorded (DP10, design §8).                                                                                                                             |
| A10 | advisory     | Req 3.4 allowed a red card edge the code does not use                                                                        | **Fixed:** Req 3.4 matches the code.                                                                                                                    |
| A11 | advisory     | FR heading agreement                                                                                                         | **Fixed** with the localization pass ("Phrases retirées / modifiées").                                                                                  |
| A12 | advisory     | The privacy page should name the stored key                                                                                  | On the pre-launch checklist.                                                                                                                            |

## For human or legal review (added to `docs/pre-launch-checklist.md`)

Naming a real paper in a labelled simulation; whether a source-update notification is a regulated function;
server logs of `/evidence/changes` and `/evidence/resolve` bodies; superseded printed notes on the doctor page;
lock-screen wording on shared devices.

**Verdict:** blocked on A1–A3 → fixed; merge with A8, A9, A12 tracked.
