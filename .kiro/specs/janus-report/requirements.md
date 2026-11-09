# Requirements: Janus report (the Summary screen and the shareable summary image)

> Owner request 2026-11-09 (enhancement item 2 of 6). Client only (`apps/web`); no API change. Builds on the
> card system of `experience` Req 29 (DP50–DP56) and keeps every rule of `experience` (Req 1, 7, 14, 15, 28).
> Property numbers P1–P9 and decision numbers DP1–DP13 are this spec's own; upstream ones are written
> "experience DPn", "experience Req n".

## Introduction
After a check, the person sees one calm screen that sums up the result at a glance, in the manner of the Apple
Health summary: how many medicines were checked, how many prescribing-cascade patterns are worth discussing and how
sure the order of each is, which medicines carry the abrupt-stop line, where the boxes come from, and how fresh the
sources are. Every tile leads to the screen that holds the detail. The person can also make a small image of the
summary to send to a relative or show a doctor; by default it holds counts only.

The Summary decides nothing. Every number is a count of what the evaluation result, the list or the evidence
resolution already say (experience DP3: the client computes no medical result).

## Glossary
- **Summary:** the screen of this spec (`/results/summary`). The word "report" is not used for it, because each
  language reserves its word for a report (EN report, TR bildirim …) for FAERS and donated reports (experience
  Req 28.4).
- **Timing group:** the order wording of experience Req 28.1 that a finding's `timing` maps to: "Order fits the
  pattern" (`within_window`), "Order fits, later than the usual window" (`after_window`), "Order not confirmed"
  (`same_month`, `date_unknown`).
- **Warned item:** a list item named in `item_warnings` (`do_not_stop_suddenly`).
- **Not fully checked:** a list item with at least one `not_checked` entry (one of its ingredients cannot be checked).
- **Share image:** a PNG made in the browser from the summary; it leaves Janus only through the person's own share
  or save action.

## Requirements

### Requirement 1: The Summary screen and how to reach it
**User story:** As a patient after a check, I want one screen that tells me the result at a glance, so that I know
what to look at and what to bring to my doctor.
1. THE client SHALL provide the route `/results/summary` with one large title (`h1`) and one summary line, in every
   locale; the route SHALL be a wide route (experience Req 27) and SHALL keep the Results tab active.
2. WHEN a result is shown on `/results` THE client SHALL show a link to the Summary directly under the large title.
3. THE Summary SHALL start with a back link to Results and SHALL use the evaluation of the current list (the same
   cached evaluation as `/results`, experience DP29); it SHALL NOT start a second evaluation of the same input.
4. WHILE the evaluation loads, fails, is blocked (empty list, too many, needs confirmation) or the rule base is
   unavailable, THE Summary SHALL show the same loading, empty and error states as `/results`.

### Requirement 2: What the Summary shows
**User story:** As a patient, I want the key numbers large and each one explained in a sentence, so that I can read
the result in seconds and still know exactly what each number means.
1. THE Summary SHALL show the number of medicines in the list, split into fully checked and not fully checked; THE
   sentence SHALL name both numbers; THE tile SHALL link to `/medicines`.
2. THE Summary SHALL show the number of findings and SHALL count every finding in exactly one timing group; each
   group SHALL show its order wording and its number; each finding SHALL be listed under its group by its title
   and SHALL link to its finding detail (`/results/finding#<position>`); the tile SHALL link to `/results`; the
   tile SHALL carry "This may be worth discussing with your doctor." when there is a finding.
3. WHERE findings have an unconfirmed product form, THE patterns tile SHALL say how many (experience Req 14.4); it
   SHALL NOT form a fourth timing group.
4. THE Summary SHALL show the number of warned items, the box name of each and, under each name, the existing
   abrupt-stop line ("Do not stop this medicine suddenly.", `AbruptStopLine`) exactly once per warned item; the
   tile SHALL link to `/medicines`. WHEN there is no warned item the tile SHALL NOT be shown.
5. THE Summary SHALL show the regions of the boxes as counts per region (Türkiye, European Union, United States,
   and "added by name" for an ingredient chosen by name); the counts SHALL add up to the number of medicines; the
   tile SHALL link to `/passport`.
6. THE Summary SHALL show the freshness of the sources: each product source of the list with its snapshot date
   (as the passport shows it, "TİTCK, data of 6 Nov 2026"), the patterns checked ("Janus checked 63 of the 65
   patterns of the PIPC list"), and the integrity line of the evidence of all findings: the number of sources,
   the stale sources with their dates, and "No retracted source was used." only WHEN the integrity line of every
   finding says so; otherwise the number of findings with excluded evidence. The evidence part SHALL link to the
   first finding's detail (where the evidence is shown) and SHALL have its own loading and error states.
7. THE Summary SHALL show the date of the check (the result's `as_of_month`) in the interface language.

### Requirement 3: Visual encoding
**User story:** As a colour-blind or low-vision patient, I want the shapes to carry the meaning with words and
numbers, so that nothing depends on telling two colours apart.
1. THE medicines, patterns and patterns-checked tiles SHALL show a ring (inline SVG) whose segments are told apart
   by stroke pattern (solid, dashed, dotted) as well as tone, with a legend that repeats the pattern, the label
   and the number; the regions tile SHALL show a segmented bar with the same rule.
2. EVERY chart SHALL be `aria-hidden` and SHALL be accompanied by the sentence with the same numbers (experience
   DP53); every big number SHALL have its label next to it.
3. THE Summary SHALL use `--risk` only for the emergency notice and the safety lines, `--warn` only for the
   abrupt-stop line; no finding, timing group or ring segment SHALL be red or carry an assessment.
4. Motion SHALL be transform and opacity only (a ring that draws in), and none under `prefers-reduced-motion`.

### Requirement 4: Safety wording
**User story:** As a patient, I want the summary to say no more than the check supports, so that a short screen does
not read as an all-clear or a verdict.
1. WHEN the result has no finding and the statement is `no_pattern_found`, THE Summary SHALL show "Janus found no
   pattern from its rule list. This does not mean your medicines are free of problems." in place of a large zero,
   and SHALL show no reassurance word (`reassurance.ts`) in any locale.
2. WHEN any finding's event has a safety line, THE Summary SHALL show the emergency notice first and SHALL show each
   such safety line in the patterns tile.
3. THE disclaimer and the demo label SHALL stay (the shell's footer and label, experience Req 1); no text SHALL
   contain a forbidden phrase in any of the five languages.
4. THE timing wording SHALL be the order wording of experience Req 28.1; the engine codes `probable` / `possible`
   SHALL NOT be shown.

### Requirement 5: The share image
**User story:** As a patient, I want to send a picture of the summary to a relative or show it to my doctor, and
decide myself what it contains.
1. THE Summary SHALL offer "Share a summary image"; THE image SHALL be generated in the browser as a PNG
   (1080 × 1350 px) from a text model; nothing SHALL be sent to a server to make, preview or share it.
2. BY DEFAULT THE image SHALL contain counts only: the number of medicines checked, the number of patterns to
   discuss, "checked against n of m patterns", the number of medicines with the abrupt-stop line together with
   the sentence "Do not stop this medicine suddenly.", and the month of the check; it SHALL contain no box name,
   no ingredient name and no event name.
3. THE person MAY add the event names of the patterns and, separately, the ingredient names of the list, each with
   a checkbox that is off by default and a sentence explaining what will be added; box names SHALL never be on the
   image. WHEN event names are added and an event has a safety line, THE image SHALL carry that safety line with
   the user region's emergency number.
4. THE image SHALL always carry the disclaimer, the zero-state sentence of Req 4.1 when there is no finding, and,
   in demo mode only, "Demo · synthetic patient".
5. BEFORE the image leaves the page, THE client SHALL show a confirmation step with the exact image (the same PNG)
   and the sentence that the image leaves Janus only through the person's own sharing or saving and may contain
   health information; only an explicit "Share" or "Save image" action SHALL hand the image over.
6. WHERE the Web Share API can share files (`navigator.canShare({ files })`), THE client SHALL use it; otherwise THE
   client SHALL download the PNG (`janus-summary-YYYY-MM.png`). A cancelled share SHALL leave the confirmation open
   and SHALL NOT show an error.
7. THE confirmation SHALL be a modal dialog (native `<dialog>`): focus moves into it, Escape and Cancel close it,
   focus returns to the button that opened it; the preview SHALL have an alternative text with the image's text.

### Requirement 6: Quality
1. EVERY text SHALL be in the `Report` namespace in five languages (natural wording, the fixed report word where a
   report is meant), with key parity and no empty strings.
2. THE Summary and the confirmation SHALL pass axe (WCAG 2.2 A/AA), have no horizontal scroll and 44 px targets at
   375 px and 1280 px, in both themes; Glass Janus SHALL show no theme-device word.
3. IN demo mode, opening the Summary, the confirmation and the share SHALL make no request to the API and no request
   to another origin.
4. THE Summary SHALL read well with long names (long box names wrap, many findings stay in their group).
