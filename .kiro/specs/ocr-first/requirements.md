# Requirements: OCR first — a box from any country

> Owner request 2026-11-10. Extends `experience` Requirements 10–12 (scan, label recognition, confirm) in
> `apps/web`. No API change, no new data source, no database change. It changes no cascade, memory or resolution
> logic: the device only proposes ingredient names; the API resolves the chosen name as before.

## Introduction
Janus can look a box's code up only for the countries whose product lists it holds. The name of the ingredient is
printed on every box in every country, and the accepted ingredient names of five languages are already in the
client. This spec makes that path first-class: the three ways in (code, label photo, name) are shown side by side,
a code that cannot be used leads straight to the other two, and a label photo is turned on the device into a short
list of ingredient candidates that the user confirms.

The claim Janus makes is exactly this: **the label photo and the ingredient name work with a box from any
country, as long as the name is printed in Latin letters.** It does not claim that every ingredient is in Janus's list, that every photo is read correctly, or that
codes from every country can be looked up.

## Glossary
- **Held name:** an ingredient name of the client vocabulary (`apps/api/janus/notes/glossary/ingredients.csv`,
  status `accepted`) in English (with its alternative English name), Turkish, German, French or Spanish.
- **Device list:** the held names by ingredient key, generated into `apps/web/src/vocabulary/ingredient-names.json`.
- **Folding:** lower case, diacritics removed, `ı ß æ œ ø ł đ` spelled with ASCII letters.
- **Skeleton:** a folded word after the spelling rules of design §3.2 (the same INN in different languages gives
  the same skeleton in most cases).
- **Salt word:** a salt, ester or hydrate word of design §3.3 (hydrochloride, besilat, sodique, …).
- **Candidate:** an ingredient key proposed for a label, with its strength (`exact`, `variant`, `close`), its edit
  distance and the words as printed.
- **Cap:** the longest tolerated edit distance for a held name: 0 below 6 letters of skeleton, 1 for 6–8, 2 from 9.
- **Reading:** one run of the recogniser over the photo, upright or turned by quarter turns.

## Requirements

### Requirement 1: Three ways in, and no dead end
**User story:** As a caregiver with a box Janus has no product list for, I want to be shown what still works,
so that I can add the medicine anyway.

1. THE scan screen SHALL present the three ways — scan the code, photograph the label, type the name — as three
   equal controls of one group, each with an icon and a text, each at least 44 × 44 px, and SHALL say in text that
   the label photo and the ingredient name work with a box from any country when the name is printed in Latin
   letters, and that the code works for the countries whose product lists Janus holds.
2. THE panel of each way SHALL begin with one sentence that says what that way does; THE label panel SHALL also
   say that Janus reads Latin letters only and can misread a word.
3. WHEN a resolution of a code, an NDC or a name has no candidate (`not_found`) THE confirm screen SHALL keep the
   "not found" statement with the regions and sources searched (`experience` Req 12.6) and SHALL offer the label
   photo and the name search as actions that open the scan screen on that way, worded as other ways to try, not
   as a promise that the box will be found.
4. WHEN a resolution carries `no_open_product_database` or `region_adapter_not_available` without a candidate THE
   confirm screen SHALL offer the same two actions; it SHALL NOT word `no_open_product_database` as "not found"
   (`experience` Req 12.5 unchanged).
5. WHEN on the scan screen a code is unreadable, a typed national code cannot be looked up as a code, no code is
   found in a photo, no code is found by the camera within 15 seconds, or the camera is not available or not
   permitted, THE client SHALL show the message and, with it, the label photo and the name as actions.
6. THE home screen and the start screen SHALL say that the label photo and the ingredient name work with a box
   from any country that prints the name in Latin letters, and SHALL NOT say or imply that Janus looks up codes
   from every country, knows every ingredient or reads every photo correctly.

### Requirement 2: Ingredient candidates from the label photo
**User story:** As a user, I want Janus to find the ingredient name in the photo, so that I do not have to pick
the right words out of everything printed on the box.

1. AFTER a label photo is read THE client SHALL show, first, the ingredient candidates found on the device
   (Requirement 3), each with the ingredient's name by the vocabulary rule (`experience` Req 2.5) and the words as
   printed on the label including their salt words.
2. A candidate of strength `close` SHALL carry a visible note that the spelling is similar and should be compared
   with the box.
3. THE client SHALL NOT select, confirm or send any candidate by itself. No state of the label result SHALL hold a
   chosen candidate; a request SHALL be made only from a choice of the user.
4. WHEN the user chooses a candidate THE client SHALL send `POST /resolve/search` with the English held name of
   that ingredient as the query, the scan region as set, and nothing else from the label. The medicine enters the
   list only after the confirm screen (`experience` Req 12.1).
5. THE words of the label SHALL stay available to tap (`experience` Req 11.2 unchanged), folded behind a disclosure
   when candidates exist and open when none exists, for a product name or an ingredient the device list does not
   hold. NDC shapes SHALL be offered as before.
6. ON the confirm screen that follows a candidate choice, the ingredient candidate of the chosen key SHALL be
   listed first. It SHALL NOT be preselected.
7. WHEN the label names several ingredients THE client SHALL show every candidate, SHALL say that they are added
   one after the other, and SHALL keep the result in memory until the next photo, until the user removes it or
   until the tab is closed, so that the user can come back for the next ingredient. A candidate whose ingredient
   is already in the list SHALL say so.
8. WHEN the photo is read and no ingredient candidate is found THE client SHALL say that no ingredient name from
   Janus's list was recognised — not that the medicine does not exist — and SHALL offer the words, another photo
   and typing.
9. THE client SHALL show at most five candidates at first, strongest first, and the rest on request.

### Requirement 3: Matching recognised text to ingredient names
1. Matching SHALL run on the device over the device list, as a pure function of the recognised lines.
2. Matching SHALL be invariant to letter case and to diacritics: a held name SHALL be found written in upper
   case, in lower case, with Turkish dotted/dotless capitals, and without its marks; any text SHALL give the same
   candidates in any letter case.
3. A word or phrase equal to a held name after folding SHALL give an `exact` candidate; one equal after the
   skeleton rules SHALL give a `variant` candidate (INN variants between languages, including languages Janus
   holds no name for; paracetamol and acetaminophen are one ingredient through the held alternative name).
4. Salt words SHALL be ignored for matching and shown in the printed text of the candidate, also when written as
   one word with the name (German compounds). A held name that itself consists of salt words (calcium carbonate)
   SHALL still be found. A salt word alone SHALL NOT give a candidate next to another ingredient.
5. A single word within the cap of a single-word held name SHALL give a `close` candidate. THE cap SHALL never
   exceed 2 and SHALL be 0 for names shorter than 6 letters. Multi-word names SHALL NOT be matched tolerantly.
6. WHEN an exact or variant match exists for a span THE matcher SHALL NOT also propose a `close` candidate for
   that span. WHEN more than three ingredients tie at the smallest distance for a word THE matcher SHALL propose
   none for it.
7. Adding characters that are not letters around a word, and words farther than the cap from every held name,
   SHALL NOT produce a candidate.
8. EVERY ingredient named on a combination label SHALL be a candidate, once each, in the order strongest first
   and then as printed.
9. Two keys with the same English held name SHALL be one candidate.

### Requirement 4: Reading the photo
1. THE label photo SHALL come from the camera (a live picture with a "take the photo" control) or from a photo the
   user picks. WHEN the camera is missing or permission is refused THE client SHALL say so and keep the photo
   picker and typing usable.
2. WHILE a photo is read THE client SHALL show a status with the progress in percent and a progress bar, SHALL
   mark it busy for assistive technology, and SHALL disable starting another reading.
3. WHEN the upright reading gives no candidate and no NDC and the recogniser's confidence is below 75 THE client
   SHALL read the photo again turned by one quarter, three quarters and one half turn, stop at the first reading
   that gives a candidate or an NDC, and else use the most confident reading. Otherwise it SHALL read once.
4. IF reading fails THEN THE client SHALL say that the label could not be read on this device and offer typing.
   IF no text is recognised THEN it SHALL say so and offer another photo and typing.
5. A photo larger than 2,600 px on its long side SHALL be reduced on the device before reading.

### Requirement 5: Measured, reproducible evaluation
1. THE repository SHALL hold a generator of synthetic label images (rendered text in several fonts, sizes,
   rotations, colours; Turkish, German, French and Spanish diacritics; other Latin-script languages; combination
   labels; labels without a held ingredient). No real product photo SHALL be downloaded or committed.
2. THE recognised text of those images SHALL be recorded with the app's recogniser, models and options and
   committed, so that the matching numbers can be reproduced without the images.
3. A test SHALL compute, on the recorded text, the ingredient hit rate before (one upright reading, a printed
   word equals a held name apart from letter case) and after (the reading rule of Requirement 4.3 with the matcher
   of Requirement 3), by group, and the share of labels with a wrong candidate; it SHALL fail when the numbers
   differ from the committed results or when "after" is worse than "before" in any group.
4. THE report SHALL say that the images are synthetic and are not photos of real boxes.

### Requirement 6: Privacy unchanged
1. THE photo, the recognised text, the candidates and the printed words SHALL stay on the device. THE only text
   sent from a label SHALL be what the user chose: the English held name of a chosen candidate, a chosen NDC, or
   the chosen adjacent words (`experience` Req 11.2, 23.2).
2. THE photo SHALL be dropped when it has been read. THE label result SHALL live in memory only, SHALL never be
   written to storage, and SHALL be cleared by "Delete everything on this device" and when the demo starts.
3. THE privacy page SHALL stay true: it already says that photos and recognised text stay on the device and that
   the words the user types or chooses for a search are sent.

### Requirement 7: Languages, themes, accessibility
1. EVERY new text SHALL exist in English, Turkish, German, French and Spanish with the same meaning, and SHALL use
   each language's one term for "ingredient" (etkin madde, Wirkstoff, substance active, principio activo).
2. THE screens SHALL work in both themes at 375 px and 1280 px without horizontal scroll, with touch targets of at
   least 44 × 44 px, visible focus, and no WCAG 2.2 AA violation reported by axe in any state of Requirements 1–4.
3. No new text SHALL use "AI"; recognition is described as reading on this device. No text SHALL imply that a
   person reviewed a candidate.
4. No new text SHALL advise on a medicine or reassure about one (`medical-safety.md`).
