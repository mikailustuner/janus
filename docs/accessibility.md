# Accessibility

Target: WCAG 2.2 level AA on every page, in the six languages and both themes. This page says what is checked
automatically, what was found and fixed, and the manual screen-reader audit that has not been done yet.

## Checked automatically (CI)

| Check | Where | Covers |
|---|---|---|
| axe (WCAG 2.0, 2.1, 2.2 A and AA rules) | `apps/web/e2e/routes.spec.ts` and the page specs | every route, six locales, both themes, phone and desktop widths |
| Touch targets of 44 × 44 px or more | `routes.spec.ts` | every route |
| No horizontal scroll at 375 px, large text at 19 px | `routes.spec.ts`, `offline.spec.ts`, `states.spec.ts` | every route; long German text |
| Reduced motion and reduced transparency | `offline.spec.ts` | the animated scenes, the glass theme |
| Skip link moves focus to the content | `keyboard.spec.ts` | patient and researcher pages |
| Visible focus indicator on every focused control (2.4.7) | `keyboard.spec.ts` | nine pages, tabbing through each |
| Focused control not hidden behind a fixed bar (2.4.11) | `keyboard.spec.ts` | the same nine pages, phone and desktop |
| No positive `tabindex`; heading levels never skip; the page has one `h1` | `keyboard.spec.ts`, `patient-states.spec.ts` | the same pages; every patient screen in its empty and error states |
| Disclosures and the language select work from the keyboard | `keyboard.spec.ts` | |
| Both menus reachable by keyboard | `navigation.spec.ts` | patient and researcher menus |

Automated checks find only part of the problems; they cannot judge whether a text read aloud makes sense, or
whether the order in which a screen reader announces a page is the order a person needs.

## Found and fixed (plan D5, 2026-11-13)

- **Focus hidden behind the bottom bar (2.4.11).** Below 768 px, tabbing to controls near the end of a page left
  them under the fixed bottom bar. The page now keeps a bottom scroll padding the size of the bar.
- **No heading on empty and error screens.** Eight screens (results, summary, finding, note, confirm, medicine
  information, two passport pages) had no `h1` when there was nothing to show or the service failed. They now keep
  their page title in every state.

## Manual audit (not done yet)

A manual audit with screen readers has not been done. It needs a person who uses a screen reader, or one who has
been trained to test with one. The checklist below is the plan for it.

| Setup | Pages |
|---|---|
| NVDA (latest) with Firefox on Windows | home, scan (typing a name), medicines, results, finding, note, settings; research hub, validation studies |
| VoiceOver with Safari on iOS | the same patient pages, in Turkish and English |
| TalkBack with Chrome on Android (optional) | home, scan, results |

For each page:
1. Landmarks: header, navigation (patient or researcher menu, named), main, footer are announced.
2. The page title and the `h1` say where the person is; the heading list gives a sensible outline.
3. Every control has a name that says what it does, in the page's language (and `lang` is right for language names).
4. The emergency line and the disclaimer are read; the result's "what you can do" part is read in order.
5. Status messages (loading, a medicine added, an error) are announced without moving focus.
6. Forms: every field has its label; errors are announced and tied to their field.
7. Zoom to 200 % and text spacing (WCAG 1.4.12): nothing overlaps or is cut off.

Findings go into issues with the page, the setup and the WCAG criterion; this page lists them once the audit is done.
