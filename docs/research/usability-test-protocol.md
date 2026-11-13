# Usability tests: protocol (plan D2.4, D3.4)

**Status:** protocol only. The tests have not been run yet; they wait for volunteers. No result is reported anywhere
until they have been run. Research prototype, not a medical device. Expert review has not yet been done.

This protocol is fixed before the first session, like the validation protocols in this folder. A change after the
first session is reported as a deviation, with the reason.

## 1. Questions

1. **Patients and families.** Can a person who takes several medicines, or who looks after someone who does, add a
   medicine list, understand what Janus found, and get the doctor note, without help?
2. **The safety-critical reading.** After reading a result, does anyone conclude that they should stop or change a
   medicine on their own? (Janus never says so; the result card says the opposite.)
3. **Researchers.** Can a researcher trace a number to its source, download a study's numbers and cite the version,
   and find how to call the API or set up the MCP server?

## 2. Design

- **Method:** moderated sessions with think-aloud: the participant says what they are thinking while they work. One
  moderator, one note-taker (they can be the same person).
- **Where:** in person or by video call with screen sharing. The participant uses their own phone or computer and the
  public site (janusmeds.org).
- **No recording:** no audio, video or screen recording. The note-taker writes notes on the form in §6 only.
- **Length:** about 30 minutes for patients, about 20 minutes for researchers.
- **Language:** the participant's language among the six site languages.
- **No health data:** patients do not enter their own medicines. They use the invented patient card in §4 (an
  invented person; the boxes are typed by name). Nothing the participant types identifies them.

## 3. Participants

| Group | Number | Who | Not eligible |
|---|---|---|---|
| Patients and families | 6–8 | Adults who take three or more medicines, or who help a family member with theirs. At least two aged 65 or more; at least two who say they are not confident with smartphones. | People who work in medicine or pharmacy |
| Researchers and clinicians | 3–5 | Pharmacists, physicians, pharmacoepidemiologists or health-data researchers | People who have worked on Janus |

Five to eight participants per group find most of the serious usability problems of a flow; the numbers are not
meant for statistical comparison. Volunteers are found by the project owner. Participation is voluntary; a
participant can stop at any time without giving a reason.

**Consent (read aloud before starting):** "This session tests the website, not you. There are no wrong answers.
Please say what you are thinking while you use it. We take written notes only; nothing is recorded. Your name is
not written on the notes; you are participant P0x. You can stop at any time. The website is a research prototype and
gives information, not medical advice. Please do not enter your own medicines today; use the card I give you. Do you
agree to take part?" The note-taker writes down the answer (yes or no) and the date.

## 4. Tasks

The moderator reads each task; the participant works without help. Help is given only when the participant asks
twice or is stuck for three minutes; the task is then scored "with help".

**Patients and families** (invented patient card: amlodipine 10 mg since January 2024; furosemide 40 mg since
March 2024; omeprazole 20 mg since January 2022):

| Task | What the participant is asked | Done when |
|---|---|---|
| P1 | "Add these three medicines to Janus." | All three are on the list with their start months |
| P2 | "Check the list. In your own words: what did Janus find, and what would you do next?" | The participant has opened the results and answered |
| P3 | "Get a note you could take to your doctor." | A note is on screen or saved as PDF |

After P2 the moderator asks three comprehension questions and writes the answers word for word:
1. "What did Janus find?" (correct: a possible pattern between two medicines, not a diagnosis)
2. "What would you do about it?" (correct: talk to the doctor or pharmacist)
3. "Would you stop one of these medicines?" (correct: no, not on my own)

**Researchers and clinicians:**

| Task | What the participant is asked | Done when |
|---|---|---|
| R1 | "Find how well Janus finds published prescribing cascades, and the document that fixed the method in advance." | The validation page and the protocol are open |
| R2 | "Download the numbers of that study and copy the citation of this version." | A CSV is saved and the citation is copied |
| R3 | "Find how to use Janus from your own code or from an assistant client (MCP)." | The API examples or the MCP setup are on screen |
| R4 | "Pick one value in the drug model kit and find where it comes from." | A source link of the value is open |

## 5. Measures

- **Task success** per task: done alone, done with help, or not done.
- **Time** per task, in whole minutes, from the end of the task text to "done" or to giving up.
- **Comprehension** (patients, after P2): each of the three answers scored correct, partly correct or wrong by the
  moderator against the correct answers above.
- **Safety-critical reading:** the number of patient participants who say they would stop or change a medicine on
  their own, after reading a result. Any such answer is a finding, whatever the other results.
- **System Usability Scale (SUS)** at the end: the standard ten items, 1 (strongly disagree) to 5 (strongly agree).
  English: Brooke J. SUS: a "quick and dirty" usability scale. In: Usability Evaluation in Industry. Taylor & Francis;
  1996. Turkish: the validated SUS-TR (Demirkol D, Şeneler Ç. A Turkish translation of the System Usability Scale:
  the SUS-TR. Uşak Üniversitesi Sosyal Bilimler Dergisi. 2018;11:237–253. doi:10.29217/uujss.495). Other languages:
  the English items, read in the participant's language by the moderator, noted as such.
- **Problems:** each observed problem with the screen, what happened and a severity from 0 to 4 (0 = not a problem,
  4 = prevents the task or could lead to harm).

**Targets (fixed now):** each task done alone by at least 80 % of the group; mean SUS of 68 or more (the usual
average); no participant reads a result as advice to stop or change a medicine. The results are reported against
these targets, met or not.

### SUS items

| # | English (Brooke 1996) | Türkçe (SUS-TR) |
|---|---|---|
| 1 | I think that I would like to use this system frequently. | Bu sistemi sıklıkla kullanmak isteyeceğimi düşünüyorum. |
| 2 | I found the system unnecessarily complex. | Bu sistemi gereksiz bir şekilde karmaşık buldum. |
| 3 | I thought the system was easy to use. | Bu sistemin kullanımının kolay olduğunu düşündüm. |
| 4 | I think that I would need the support of a technical person to be able to use this system. | Bu sistemi kullanabilmek için daha teknik bir kişinin desteğine ihtiyaç duyacağımı düşünüyorum. |
| 5 | I found the various functions in this system were well integrated. | Bu sistemdeki çeşitli fonksiyonları iyi entegre edilmiş buldum. |
| 6 | I thought there was too much inconsistency in this system. | Bu sistemde çok fazla tutarsızlık olduğunu düşündüm. |
| 7 | I would imagine that most people would learn to use this system very quickly. | Birçok insanın bu sistemi kullanmayı çok çabuk öğreneceğini sanıyorum. |
| 8 | I found the system very cumbersome to use. | Bu sistemin kullanımını çok elverişsiz buldum. |
| 9 | I felt very confident using the system. | Bu sistemi kullanırken kendimden çok emin hissettim. |
| 10 | I needed to learn a lot of things before I could get going with this system. | Bu sistemde bir şeyler yapabilmek için öncelikle bir çok şey öğrenmem gerekti. |

Scale: 1 = strongly disagree / Hiç katılmıyorum … 5 = strongly agree / Tamamen katılıyorum.

## 6. Notes form and analysis

One row per participant in a CSV kept outside the repository:

`participant, group, language, device, date, consent, p1, p1_min, p2, p2_min, p3, p3_min, c1, c2, c3, stop_reading,
q1, …, q10, problems`

(for researchers `r1` … `r4` in place of `p1` … `p3` and no `c` columns). Task cells are `alone`, `help` or `not_done`.

**Analysis.**
- Task success: counts per task (for example "6 of 7 alone"). With these group sizes the counts are reported without
  percentages or tests.
- SUS: scored with `pipelines/tools/sus_score.py` (standard scoring; n, mean, median and range).
- Problems: grouped by screen and severity. Every problem of severity 3 or 4 gets an issue, and the fix is checked in
  the next session.
- The report goes in `docs/research/usability-tests.md`, with the targets met or not, and without any information that
  could identify a participant.
