# Requirements: Zombie Alert ("a source of your note was retracted")

> Written 2026-11-09 as enhancement item 3 of 6 (owner-approved). Builds on `evidence-integrity`
> (Req 5, 7: citability, `POST /evidence/changes`, `POST /evidence/resolve`) and `doctor-loop`
> (the note document). Web only: no API route is added or changed. Glass Janus wording is a plain
> "source update" / "Retracted"; the zombie word appears only in the Night Pharmacy (Two Faces)
> theme, where the zombie stamp already lives (design.md theme devices).

## Introduction

A doctor note is correct on the day it is made. Retractions arrive later: a paper Janus cited can
be retracted weeks after the patient printed the note. Evidence Integrity already keeps retracted
sources out of every new note; nothing told the patient that a note they had already made rested
on a source that has since been retracted. Zombie Alert watches the sources of the patient's last
note from the browser, tells the patient plainly when one is retracted, and rebuilds the note
without it, showing what changed.

## Glossary

- **Cited ids:** the evidence ids of every sentence of the last note made on this device (claim,
  statistic, medicine and integrity sentences), kept in the browser only. The integrity sentences
  list every source used, root sources included, so a retraction of a root paper is matched too.
- **Kept sentences:** id, text and evidence ids of the note's sentences that cite at least one
  evidence id (integrity section excluded), in the note's first language, kept in the browser
  only, so that a removed sentence can be shown after the update.
- **Non-citable change:** an entry of `POST /evidence/changes` whose `to_status` makes the record
  non-citable. Under evidence-integrity Req 5.2/5.3 that is `retracted` only (`corrected`,
  `expression_of_concern` and `unknown` stay citable and carry a notice in the next note).
- **Change key:** `evidence_id|to_status|observed_on`; one key alerts at most once.
- **Check:** one request to `POST /evidence/changes` and the local comparison of its answer.
- **Zombie document:** `janus.v1.zombie` in local storage (versioned, validated, safe fallback).

## Requirements

### Requirement 1: What the browser keeps

#### Acceptance criteria

1. WHEN a doctor note document is received outside demo mode THE client SHALL store in the zombie
   document the cited ids, the kept sentences, the note language and the local date the note was
   made, replacing the previous note's data.
2. THE client SHALL keep this data only in the browser and SHALL NOT send the kept sentences
   anywhere.
3. IF the stored zombie document is missing, of another version or invalid THEN THE client SHALL
   start from an empty document and SHALL NOT throw; IF storage fails THEN THE client SHALL keep
   the data for the session (SafeStorage fallback) and the app SHALL keep working.
4. WHEN the patient uses "Delete everything on this device" THE zombie document SHALL be deleted
   with the other Janus keys.
5. THE number of kept sentences SHALL be bounded (300), and so SHALL the number of kept change
   keys (500, oldest dropped).

### Requirement 2: When and how the client checks

#### Acceptance criteria

1. WHEN the app is opened outside demo mode, cited ids exist, and no check was made in the last
   hour THE client SHALL run one check.
2. WHILE the app stays open and visible THE client SHALL run a check when the last check is
   24 hours old or older; WHILE the page is hidden THE client SHALL NOT check, and WHEN it becomes
   visible again THE client SHALL check if one is due.
3. THE check request SHALL be `POST /evidence/changes` with a body of exactly `since` (the server
   date of the last successful check, else the date seven days before the note was made: no
   exact date of a health action is sent, safety audit A6) and `limit`; it SHALL
   contain no evidence id, medicine, ATC code, event or name.
4. WHEN the answer is received THE client SHALL compare only the stored cited ids with the
   changes; no other id SHALL be compared or stored.
5. IF the answer holds as many changes as the limit (possibly truncated) THEN THE client SHALL
   take the oldest `observed_on` of the answer as the next `since`, so the next check reads on
   from there; it SHALL NOT send any id to make up for it (safety audit A3).
6. IF a check fails (network, timeout, 4xx, 5xx, contract) THEN THE client SHALL show nothing,
   keep its state unchanged except the attempt time, and try again at the next due time.
7. WHEN there are no cited ids or the app is in demo mode THE client SHALL make no request.

### Requirement 3: The alert

#### Acceptance criteria

1. THE client SHALL raise an alert if and only if a cited id has a non-citable change whose change
   key it has not alerted before.
2. THE same change key SHALL NOT alert twice, across checks, reloads and overlapping answers.
3. WHILE an alert is open THE home, results and note screens SHALL show an alert card that names
   the source (title, else the evidence id), its DOI as a link, the plain status "Retracted", and
   a way to update the note. The emergency notice SHALL stay first on every screen.
4. THE alert card SHALL use the `--risk` colour only for the "Retracted" status and its icon (design.md allows red for retracted evidence), never for running text.
5. THE alert card SHALL carry no medicine name, event name or ATC code, and SHALL say that Janus
   no longer uses the source and that the alert alone is no reason to change a medicine without
   the doctor or pharmacist (medical-safety rules 1, 3).
6. Glass Janus texts SHALL contain no theme-device word (`themeWords`); Two Faces may say "zombie".

### Requirement 4: Notification (opt-in)

#### Acceptance criteria

1. THE Settings screen SHALL offer a switch to be told by a notification when a source of the
   doctor note is retracted, off by default.
2. WHEN the patient turns the switch on THE client SHALL ask the browser's notification permission
   in that tap, and at no other moment; IF permission is denied or unsupported THEN the switch
   SHALL stay off and say why.
3. WHEN an alert is raised and the switch is on and permission is granted THE client SHALL show one
   local notification with the localized text "A source in your doctor note was retracted. Open
   Janus to update the note." (demo: "Demo simulation: no source was really retracted…") It SHALL contain no medicine name, PT name, event, ATC code or
   source title (medical-safety: no notification text contains a PT name).
4. THE notification SHALL be shown through the service worker registration when there is one (so
   it works on Android), else through `Notification`; a click SHALL open the note screen.
5. THE Settings text SHALL say honestly when Janus checks: when it is opened and once a day while
   it is open, not while it is closed.

### Requirement 5: Updated note and what changed

#### Acceptance criteria

1. WHEN the patient chooses "Update the note" THE client SHALL clear the in-memory results,
   evaluate the list again and request a new note document; the API leaves the retracted source
   out (evidence-integrity Req 1.3, 5.4).
2. WHEN the new note is received THE client SHALL show "What changed": the source (title, DOI link,
   the retraction notice DOI or link when known), each kept sentence that cited it and is no longer
   in the note ("removed"), and each that is still there with other text or sources ("changed",
   with the new text). It SHALL say that a doctor who already has the earlier note should
   get the updated one (safety audit A7).
3. WHEN the note is updated THE alert SHALL close on every screen and the new note's ids SHALL
   replace the stored ones.
4. THE notice DOI or link SHALL come from `POST /evidence/resolve` with the changed ids only, made
   during the update (the update already sends the medicine list for the new note, so the ids add
   no new information); IF it fails THEN the paper DOI link alone SHALL be shown.
5. The patient SHALL be able to dismiss an alert or the "What changed" card.

### Requirement 6: Demo mode

#### Acceptance criteria

1. IN demo mode THE client SHALL make no network request for this feature and SHALL write nothing
   to local storage (the demo state, the notification opt-in included, is in memory and ends with
   the session).
2. THE demo note screen SHALL offer "Simulate a source retraction (demo)" once a note is shown;
   WHEN chosen THE client SHALL raise exactly one alert from the fixture
   `src/demo/fixtures/zombie.json` through the same comparison as a live check; choosing it again
   SHALL NOT raise a second alert.
3. THE simulated change SHALL be labelled as simulated wherever it is shown, before the source's
   title, in the heading and in the "Retracted (simulated)" label (safety audit A1, A2) ("Simulated in the
   demo: this source has not been retracted"), and its notice DOI SHALL use the Crossref test
   prefix `10.5555` so it cannot be mistaken for a real notice.
4. WHEN the demo note is updated THE client SHALL apply the evidence-integrity rule (Req 5.4: keep
   only citable ids; a sentence left without any is removed) to the recorded note for the
   simulated id, and SHALL show "What changed" as in Requirement 5.
5. A notification in demo mode SHALL follow Requirement 4 (local only, no request).

### Requirement 7: Quality

#### Acceptance criteria

1. Every new text SHALL be in the new `ZombieAlert` namespace in the five locales, pass the
   forbidden-phrase, reassurance and theme-word tests, and be reviewed by the
   localization-reviewer and the safety-auditor.
2. The alert, the "What changed" card and the Settings switch SHALL pass axe (WCAG 2.2 AA), have no
   horizontal scroll and targets of at least 44 px at 375 and 1280 px, in both themes.
3. The pure logic SHALL be covered by fast-check properties (design §5).
