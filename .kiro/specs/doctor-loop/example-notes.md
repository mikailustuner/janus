# Example notes (synthetic patient)

Generated on 2026-11-08 from the committed glossary, the development database (dataset `7db3a513…`) and the FAERS counts, by `POST /notes/document`, one language per request. The list is invented: seven ingredient items (no product names), start months set by hand. It exists to read the wording in each language; it is not a clinical example and is regenerated, not edited. Statistics use region EU. Section ids are shown as headings; ingredient items have no product line.


---

## English (en)


### header

- Prepared in 11/2026 by Janus from the medicines entered by the patient or a caregiver.
- This note lists published prescribing-cascade patterns that match the patient's medicines, with their sources. It is meant to support a conversation with the patient and does not replace clinical judgment.
- Janus provides information, not medical advice. Research prototype — not a medical device.

### medicines

- amlodipine [C08CA01]; Started: 03/2025
- furosemide [C03CA01]; Started: 06/2025
- esomeprazole [A02BC05]; Started: 01/2025
- cyanocobalamin [B03BA01]; Started: 08/2025
- metoclopramide [A03FA01]; Started: 02/2025
- haloperidol [N05AD01]; Started: 05/2025 — Do not stop this medicine suddenly.
- imipenem [J01DH51] (combination code); Start date not known

### findings

- Nothing to show in this section.

### findings_form_unconfirmed

- For these medicines the exact product (for example tablet or eye drops) was not confirmed, so every form of the ingredient was considered. Please check which product the patient uses.
- Match with the published prescribing-cascade pattern Calcium channel blocker → Peripheral edema → Diuretic (PIPC list, row 5): amlodipine and furosemide.
- Months from the start of amlodipine to the start of furosemide: 3. This is within the 12-month window commonly used in prescription sequence symmetry analysis.
- The same cascade is also described in another published cascade list (ThinkCascades).
- A correction has been published for a source of this pattern.
- This pattern may be worth reviewing with the patient.
- Match with the published prescribing-cascade pattern Proton pump inhibitor → Vitamin or Mineral Deficiency → Vitamin or Mineral Deficiency (PIPC list, row 49): esomeprazole and cyanocobalamin.
- Months from the start of esomeprazole to the start of cyanocobalamin: 7. This is within the 12-month window commonly used in prescription sequence symmetry analysis.
- Row 49 of the PIPC list names the second step as published, and it repeats the adverse event. Janus checks vitamin B12, magnesium and oral iron supplements for this row.
- A correction has been published for a source of this pattern.
- This pattern may be worth reviewing with the patient.

### statistics

- All regions: 424 reports name amlodipine with the event “Peripheral edema”; reporting odds ratio (ROR) 5.14 (confidence interval 4.65 to 5.67). The event appears in a larger share of the reports that name this medicine than in the other reports that name a recognized medicine.
- European Union: 100 reports name amlodipine with the event “Peripheral edema”; reporting odds ratio (ROR) 5.63 (confidence interval 4.57 to 6.93). The event appears in a larger share of the reports that name this medicine than in the other reports that name a recognized medicine.
- All regions: 147 reports name esomeprazole with the event “Vitamin or Mineral Deficiency”; reporting odds ratio (ROR) 20.7 (confidence interval 17.4 to 24.5). The event appears in a larger share of the reports that name this medicine than in the other reports that name a recognized medicine.
- European Union: 108 reports name esomeprazole with the event “Vitamin or Mineral Deficiency”; reporting odds ratio (ROR) 21.3 (confidence interval 17.2 to 26.3). The event appears in a larger share of the reports that name this medicine than in the other reports that name a recognized medicine.
- Reports are sent voluntarily and are not verified.
- The counts do not show how often an event happens.
- Only repeated versions of the same case are merged, so one event can still appear in more than one case.
- This is a screening statistic. Many medicine–event pairs are examined at once and most of them meet these criteria, so meeting them is common and is not evidence that the medicine causes the event.
- No reports, or a pattern that is not clear, does not mean there is no association or that the patient's medicines are free of problems.
- Counts cover reports received or updated in the four quarters 2025Q4–2026Q3, including follow-up versions of cases first received earlier.
- Counts use only reports that name at least one medicine Janus recognizes (84.8% of the reports in this window). Some spellings are not recognized, so a pattern can be missed.
- Source: FDA AEMS (formerly FAERS), snapshot 2026-10-28. Not an FDA endorsement.
- MedDRA® the Medical Dictionary for Regulatory Activities terminology is the international medical terminology developed under the auspices of ICH. MedDRA® trademark is registered by IFPMA on behalf of ICH.

### scope

- Janus checked 63 of the 65 prescribing-cascade patterns of the PIPC list.
- Row 27 (Cholinesterase inhibitor → Gastrointestinal upset → Bismuth subsalicylate) cannot be checked.
- Row 57 (Urinary anticholinergic → Dry mouth → Saliva substitute) cannot be checked.

### integrity

- Sources used: 4, of which 3 were checked against retraction data by DOI.
- Status of the checked sources: no notice 2, correction 1, expression of concern 0, not yet checked 0.
- Retraction checks were made between 2026-11-07 and 2026-11-07.
- No retracted source was used.

### about

- Versions: rules 8d4881fc, medicine data 7db3a513, evidence 8a5b888f, report counts 20261108, glossary 226aaf2e.
- Prescribing-cascade patterns: PIPC list (Rochon et al., European Geriatric Medicine 2025), licensed CC BY 4.0.
- Report counts come from the public quarterly data of FDA AEMS (formerly FAERS).
- The translations of clinical terms were reviewed by the project owner with AI assistance; they still need review by a pharmacist or physician and by native speakers.

---

## Türkçe (tr)


### header

- Janus tarafından, hastanın veya bakım verenin girdiği ilaçlardan 11.2026 tarihinde hazırlanmıştır.
- Bu not, hastanın ilaçlarıyla örtüşen ve yayımlanmış reçeteleme kaskadı örüntülerini kaynaklarıyla birlikte listeler. Hastayla yapılacak görüşmeyi desteklemek içindir; klinik değerlendirmenin yerini tutmaz.
- Janus bilgi sağlar, tıbbi tavsiye vermez. Araştırma prototipi — tıbbi cihaz değildir.

### medicines

- amlodipin [C08CA01]; Başlangıç: 03.2025
- furosemid [C03CA01]; Başlangıç: 06.2025
- esomeprazol [A02BC05]; Başlangıç: 01.2025
- siyanokobalamin [B03BA01]; Başlangıç: 08.2025
- metoklopramid [A03FA01]; Başlangıç: 02.2025
- haloperidol [N05AD01]; Başlangıç: 05.2025 — Bu ilacı aniden kesmeyin.
- imipenem [J01DH51] (kombinasyon kodu); Başlangıç tarihi bilinmiyor

### findings

- Bu bölümde gösterilecek bir şey yok.

### findings_form_unconfirmed

- Bu ilaçlarda ürünün tam olarak hangisi olduğu (örneğin tablet veya göz damlası) doğrulanmadı; bu nedenle etkin maddenin tüm formları dikkate alındı. Lütfen hastanın hangi ürünü kullandığını kontrol edin.
- Yayımlanmış reçeteleme kaskadı örüntüsüyle (Kalsiyum kanal blokeri → Periferik ödem → Diüretik; PIPC listesi, satır 5) örtüşme: amlodipin ve furosemid.
- Ay sayısı, amlodipin başlangıcından furosemid başlangıcına kadar: 3. Bu süre, reçete sırası simetri analizinde yaygın olarak kullanılan 12 aylık pencerenin içindedir.
- Aynı kaskad, yayımlanmış başka bir kaskad listesinde (ThinkCascades) de tanımlanmaktadır.
- Bu örüntünün bir kaynağı için düzeltme yayımlanmıştır.
- Bu örüntüyü hastayla birlikte değerlendirmek yararlı olabilir.
- Yayımlanmış reçeteleme kaskadı örüntüsüyle (Proton pompası inhibitörü → Vitamin veya mineral eksikliği → Vitamin veya mineral eksikliği; PIPC listesi, satır 49) örtüşme: esomeprazol ve siyanokobalamin.
- Ay sayısı, esomeprazol başlangıcından siyanokobalamin başlangıcına kadar: 7. Bu süre, reçete sırası simetri analizinde yaygın olarak kullanılan 12 aylık pencerenin içindedir.
- PIPC listesinin 49. satırı ikinci basamağı yayımlandığı haliyle belirtir ve bu ifade olumsuz olayı tekrarlar. Janus bu satır için B12 vitamini, magnezyum ve oral demir takviyelerini kontrol eder.
- Bu örüntünün bir kaynağı için düzeltme yayımlanmıştır.
- Bu örüntüyü hastayla birlikte değerlendirmek yararlı olabilir.

### statistics

- Tüm bölgeler: 424 bildirimde amlodipin, “Periferik ödem” olayıyla birlikte yer almaktadır; bildirim olasılık oranı (ROR) 5,14 (güven aralığı 4,65 ile 5,67 arası). Olay, bu ilacı içeren bildirimlerin, tanınan bir ilaç içeren diğer bildirimlere göre daha büyük bir kısmında görülüyor.
- Avrupa Birliği: 100 bildirimde amlodipin, “Periferik ödem” olayıyla birlikte yer almaktadır; bildirim olasılık oranı (ROR) 5,63 (güven aralığı 4,57 ile 6,93 arası). Olay, bu ilacı içeren bildirimlerin, tanınan bir ilaç içeren diğer bildirimlere göre daha büyük bir kısmında görülüyor.
- Tüm bölgeler: 147 bildirimde esomeprazol, “Vitamin veya mineral eksikliği” olayıyla birlikte yer almaktadır; bildirim olasılık oranı (ROR) 20,7 (güven aralığı 17,4 ile 24,5 arası). Olay, bu ilacı içeren bildirimlerin, tanınan bir ilaç içeren diğer bildirimlere göre daha büyük bir kısmında görülüyor.
- Avrupa Birliği: 108 bildirimde esomeprazol, “Vitamin veya mineral eksikliği” olayıyla birlikte yer almaktadır; bildirim olasılık oranı (ROR) 21,3 (güven aralığı 17,2 ile 26,3 arası). Olay, bu ilacı içeren bildirimlerin, tanınan bir ilaç içeren diğer bildirimlere göre daha büyük bir kısmında görülüyor.
- Bildirimler gönüllü olarak gönderilir ve doğrulanmaz.
- Sayılar, bir olayın ne sıklıkta görüldüğünü göstermez.
- Yalnızca aynı vakanın tekrarlanan sürümleri birleştirilir; bu yüzden aynı olay birden fazla vakada yine de yer alabilir.
- Bu bir tarama istatistiğidir. Çok sayıda ilaç–olay çifti aynı anda incelenir ve çoğu bu ölçütleri karşılar; bu yüzden ölçütleri karşılamak yaygındır ve ilacın olaya neden olduğuna dair bir kanıt değildir.
- Bildirim bulunmaması ya da net olmayan bir örüntü, ilişki olmadığı ya da hastanın ilaçlarında hiçbir sorun olmadığı anlamına gelmez.
- Sayılar, 2025Q4–2026Q3 dönemindeki dört çeyrekte alınan veya güncellenen bildirimleri kapsar; daha önce alınmış vakaların takip sürümleri de dahildir.
- Sayılar yalnızca Janus'un tanıdığı en az bir ilaç adı içeren bildirimleri kullanır (bu dönemdeki tüm bildirimler içinde bunların payı: %84,8). Bazı yazımlar tanınmaz; bu yüzden bir örüntü gözden kaçabilir.
- Kaynak: FDA AEMS (eski adıyla FAERS), veri tarihi 28.10.2026. FDA tarafından desteklenmemektedir.
- MedDRA® the Medical Dictionary for Regulatory Activities terminology is the international medical terminology developed under the auspices of ICH. MedDRA® trademark is registered by IFPMA on behalf of ICH.

### scope

- Janus, PIPC listesindeki 65 reçeteleme kaskadı örüntüsünden 63 tanesini kontrol etti.
- Satır 27 (Kolinesteraz inhibitörü → Gastrointestinal yakınmalar → Bizmut subsalisilat) kontrol edilemiyor.
- Satır 57 (Üriner antikolinerjik → Ağız kuruluğu → Yapay tükürük) kontrol edilemiyor.

### integrity

- Kullanılan kaynaklar: 4; bunlardan 3 tanesi DOI ile geri çekme verilerine karşı kontrol edildi.
- Kontrol edilen kaynakların durumu: bildirim yok 2, düzeltme 1, endişe bildirimi 0, henüz kontrol edilmedi 0.
- Geri çekme kontrolleri 07.11.2026 ile 07.11.2026 arasında yapıldı.
- Geri çekilmiş hiçbir kaynak kullanılmadı.

### about

- Sürümler: kurallar 8d4881fc, ilaç verileri 7db3a513, kanıtlar 8a5b888f, bildirim sayıları 20261108, sözlük 226aaf2e.
- Reçeteleme kaskadı örüntüleri: PIPC listesi (Rochon ve ark., European Geriatric Medicine 2025), CC BY 4.0 lisanslı.
- Bildirim sayıları FDA AEMS'nin (eski adıyla FAERS) herkese açık üç aylık verilerinden alınmıştır.
- Klinik terimlerin çevirileri proje sahibi tarafından yapay zekâ desteğiyle gözden geçirilmiştir; bir eczacı veya hekim ve anadili bu dil olan kişiler tarafından da gözden geçirilmeleri gerekmektedir.

---

## Deutsch (de)


### header

- Erstellt von Janus (Stand 11.2026) aus den von der Patientin, dem Patienten oder einer betreuenden Person eingegebenen Arzneimitteln.
- Diese Information listet veröffentlichte Muster von Verschreibungskaskaden auf, die zu den Arzneimitteln der Patientin oder des Patienten passen, mit ihren Quellen. Sie soll das Gespräch mit der Patientin oder dem Patienten unterstützen und ersetzt nicht die ärztliche Beurteilung.
- Janus bietet Informationen, keine medizinische Beratung. Forschungsprototyp – kein Medizinprodukt.

### medicines

- Amlodipin [C08CA01]; Beginn: 03.2025
- Furosemid [C03CA01]; Beginn: 06.2025
- Esomeprazol [A02BC05]; Beginn: 01.2025
- Cyanocobalamin [B03BA01]; Beginn: 08.2025
- Metoclopramid [A03FA01]; Beginn: 02.2025
- Haloperidol [N05AD01]; Beginn: 05.2025 — Setzen Sie dieses Arzneimittel nicht plötzlich ab.
- Imipenem [J01DH51] (Kombinationscode); Beginn nicht bekannt

### findings

- In diesem Abschnitt gibt es nichts anzuzeigen.

### findings_form_unconfirmed

- Bei diesen Arzneimitteln wurde das genaue Präparat (zum Beispiel Tablette oder Augentropfen) nicht bestätigt, daher wurden alle Formen des Wirkstoffs berücksichtigt. Bitte prüfen Sie, welches Präparat angewendet wird.
- Übereinstimmung mit dem veröffentlichten Muster einer Verschreibungskaskade (Calciumkanalblocker → Periphere Ödeme → Diuretikum; PIPC-Liste, Zeile 5): Amlodipin und Furosemid.
- Monate vom Beginn von Amlodipin bis zum Beginn von Furosemid: 3. Das liegt innerhalb des Zeitfensters von 12 Monaten, das in Verschreibungssequenz-Symmetrieanalysen üblicherweise verwendet wird.
- Dieselbe Kaskade ist auch in einer anderen veröffentlichten Kaskadenliste (ThinkCascades) beschrieben.
- Zu einer Quelle dieses Musters wurde eine Korrektur veröffentlicht.
- Es kann sinnvoll sein, dieses Muster mit der Patientin oder dem Patienten zu besprechen.
- Übereinstimmung mit dem veröffentlichten Muster einer Verschreibungskaskade (Protonenpumpenhemmer → Vitamin- oder Mineralstoffmangel → Vitamin- oder Mineralstoffmangel; PIPC-Liste, Zeile 49): Esomeprazol und Cyanocobalamin.
- Monate vom Beginn von Esomeprazol bis zum Beginn von Cyanocobalamin: 7. Das liegt innerhalb des Zeitfensters von 12 Monaten, das in Verschreibungssequenz-Symmetrieanalysen üblicherweise verwendet wird.
- Zeile 49 der PIPC-Liste nennt den zweiten Schritt wie veröffentlicht und wiederholt dabei das unerwünschte Ereignis. Janus prüft für diese Zeile Vitamin-B12-, Magnesium- und orale Eisenpräparate.
- Zu einer Quelle dieses Musters wurde eine Korrektur veröffentlicht.
- Es kann sinnvoll sein, dieses Muster mit der Patientin oder dem Patienten zu besprechen.

### statistics

- Alle Regionen: 424 Meldungen nennen Amlodipin zusammen mit dem Ereignis „Periphere Ödeme“; Reporting Odds Ratio (ROR) 5,14 (Konfidenzintervall 4,65 bis 5,67). Das Ereignis kommt in den Meldungen, die dieses Arzneimittel nennen, in einem größeren Anteil vor als in den übrigen Meldungen, die ein erkanntes Arzneimittel nennen.
- Europäische Union: 100 Meldungen nennen Amlodipin zusammen mit dem Ereignis „Periphere Ödeme“; Reporting Odds Ratio (ROR) 5,63 (Konfidenzintervall 4,57 bis 6,93). Das Ereignis kommt in den Meldungen, die dieses Arzneimittel nennen, in einem größeren Anteil vor als in den übrigen Meldungen, die ein erkanntes Arzneimittel nennen.
- Alle Regionen: 147 Meldungen nennen Esomeprazol zusammen mit dem Ereignis „Vitamin- oder Mineralstoffmangel“; Reporting Odds Ratio (ROR) 20,7 (Konfidenzintervall 17,4 bis 24,5). Das Ereignis kommt in den Meldungen, die dieses Arzneimittel nennen, in einem größeren Anteil vor als in den übrigen Meldungen, die ein erkanntes Arzneimittel nennen.
- Europäische Union: 108 Meldungen nennen Esomeprazol zusammen mit dem Ereignis „Vitamin- oder Mineralstoffmangel“; Reporting Odds Ratio (ROR) 21,3 (Konfidenzintervall 17,2 bis 26,3). Das Ereignis kommt in den Meldungen, die dieses Arzneimittel nennen, in einem größeren Anteil vor als in den übrigen Meldungen, die ein erkanntes Arzneimittel nennen.
- Meldungen werden freiwillig eingereicht und nicht verifiziert.
- Die Zahlen zeigen nicht, wie oft ein Ereignis auftritt.
- Nur wiederholte Versionen desselben Falls werden zusammengeführt; dasselbe Ereignis kann daher weiterhin in mehreren Fällen vorkommen.
- Dies ist eine Screening-Statistik. Viele Kombinationen aus Arzneimittel und Ereignis werden gleichzeitig geprüft und die meisten erfüllen diese Kriterien. Diese Kriterien zu erfüllen ist daher häufig und kein Beleg dafür, dass das Arzneimittel das Ereignis verursacht.
- Keine Meldungen oder ein unklares Muster bedeuten nicht, dass kein Zusammenhang besteht oder dass die Arzneimittel der Patientin oder des Patienten frei von Problemen sind.
- Die Zahlen umfassen Meldungen, die in den vier Quartalen 2025Q4–2026Q3 eingegangen sind oder aktualisiert wurden, einschließlich Folgeversionen früher eingegangener Fälle.
- Die Zahlen verwenden nur Meldungen, die mindestens ein von Janus erkanntes Arzneimittel nennen (84,8 % der Meldungen in diesem Zeitraum). Manche Schreibweisen werden nicht erkannt, daher kann ein Muster übersehen werden.
- Quelle: FDA AEMS (früher FAERS), Stand 28.10.2026. Keine Billigung durch die FDA.
- MedDRA® the Medical Dictionary for Regulatory Activities terminology is the international medical terminology developed under the auspices of ICH. MedDRA® trademark is registered by IFPMA on behalf of ICH.

### scope

- Janus hat 63 der 65 Muster von Verschreibungskaskaden der PIPC-Liste geprüft.
- Zeile 27 (Cholinesterasehemmer → Gastrointestinale Beschwerden → Bismutsubsalicylat) kann nicht geprüft werden.
- Zeile 57 (Urologisches Anticholinergikum → Mundtrockenheit → Speichelersatzmittel) kann nicht geprüft werden.

### integrity

- Verwendete Quellen: 4, davon 3 über die DOI mit Rücknahmedaten abgeglichen.
- Status der geprüften Quellen: ohne Hinweis 2, Korrektur 1, Expression of Concern 0, noch nicht geprüft 0.
- Die Rücknahmeprüfungen erfolgten zwischen 07.11.2026 und 07.11.2026.
- Es wurde keine zurückgezogene Quelle verwendet.

### about

- Versionen: Regeln 8d4881fc, Arzneimitteldaten 7db3a513, Evidenz 8a5b888f, Meldezahlen 20261108, Glossar 226aaf2e.
- Muster von Verschreibungskaskaden: PIPC-Liste (Rochon et al., European Geriatric Medicine 2025), Lizenz CC BY 4.0.
- Die Meldezahlen stammen aus den öffentlichen Quartalsdaten von FDA AEMS (früher FAERS).
- Die Übersetzungen der klinischen Begriffe wurden vom Projektverantwortlichen mit KI-Unterstützung geprüft; sie müssen noch von einer Apothekerin, einem Apotheker, einer Ärztin oder einem Arzt und von Muttersprachlern geprüft werden.

---

## Français (fr)


### header

- Préparée par Janus (11/2026) à partir des médicaments saisis par le patient ou un proche aidant.
- Cette note liste les schémas publiés de cascade de prescription qui correspondent aux médicaments du patient, avec leurs sources. Elle sert de support à l'échange avec le patient et ne remplace pas le jugement clinique.
- Janus fournit des informations, pas des conseils médicaux. Prototype de recherche — pas un dispositif médical.

### medicines

- amlodipine [C08CA01]; Début : 03/2025
- furosémide [C03CA01]; Début : 06/2025
- ésoméprazole [A02BC05]; Début : 01/2025
- cyanocobalamine [B03BA01]; Début : 08/2025
- métoclopramide [A03FA01]; Début : 02/2025
- halopéridol [N05AD01]; Début : 05/2025 — N'arrêtez pas ce médicament brutalement.
- imipénème [J01DH51] (code d'association); Date de début inconnue

### findings

- Rien à afficher dans cette section.

### findings_form_unconfirmed

- Pour ces médicaments, le produit exact (par exemple comprimé ou collyre) n'a pas été confirmé ; toutes les formes de la substance ont donc été prises en compte. Merci de vérifier quel produit le patient utilise.
- Correspondance avec le schéma publié de cascade de prescription (Inhibiteur calcique → Œdème périphérique → Diurétique ; liste PIPC, ligne 5) : amlodipine et furosémide.
- Mois écoulés entre les deux débuts (amlodipine, puis furosémide) : 3. Ce délai se situe dans la fenêtre de 12 mois couramment utilisée dans l'analyse de symétrie de séquence de prescription.
- La même cascade est aussi décrite dans une autre liste publiée de cascades (ThinkCascades).
- Un erratum a été publié pour une source de ce schéma.
- Il peut être utile de revoir ce schéma avec le patient.
- Correspondance avec le schéma publié de cascade de prescription (Inhibiteur de la pompe à protons → Carence en vitamines ou en minéraux → Carence en vitamines ou en minéraux ; liste PIPC, ligne 49) : ésoméprazole et cyanocobalamine.
- Mois écoulés entre les deux débuts (ésoméprazole, puis cyanocobalamine) : 7. Ce délai se situe dans la fenêtre de 12 mois couramment utilisée dans l'analyse de symétrie de séquence de prescription.
- La ligne 49 de la liste PIPC désigne la deuxième étape telle que publiée, et elle reprend l'événement indésirable. Pour cette ligne, Janus vérifie les compléments en vitamine B12, en magnésium et en fer par voie orale.
- Un erratum a été publié pour une source de ce schéma.
- Il peut être utile de revoir ce schéma avec le patient.

### statistics

- Toutes les régions : 424 signalements citent amlodipine avec l'événement « Œdème périphérique » ; rapport de cotes de signalement (ROR) 5,14 (intervalle de confiance de 4,65 à 5,67). L'événement apparaît dans une part plus grande des signalements qui citent ce médicament que dans les autres signalements qui citent un médicament reconnu.
- Union européenne : 100 signalements citent amlodipine avec l'événement « Œdème périphérique » ; rapport de cotes de signalement (ROR) 5,63 (intervalle de confiance de 4,57 à 6,93). L'événement apparaît dans une part plus grande des signalements qui citent ce médicament que dans les autres signalements qui citent un médicament reconnu.
- Toutes les régions : 147 signalements citent ésoméprazole avec l'événement « Carence en vitamines ou en minéraux » ; rapport de cotes de signalement (ROR) 20,7 (intervalle de confiance de 17,4 à 24,5). L'événement apparaît dans une part plus grande des signalements qui citent ce médicament que dans les autres signalements qui citent un médicament reconnu.
- Union européenne : 108 signalements citent ésoméprazole avec l'événement « Carence en vitamines ou en minéraux » ; rapport de cotes de signalement (ROR) 21,3 (intervalle de confiance de 17,2 à 26,3). L'événement apparaît dans une part plus grande des signalements qui citent ce médicament que dans les autres signalements qui citent un médicament reconnu.
- Les signalements sont envoyés volontairement et ne sont pas vérifiés.
- Les chiffres ne montrent pas la fréquence d'un événement.
- Seules les versions répétées d'un même cas sont fusionnées ; un même événement peut donc encore apparaître dans plusieurs cas.
- Il s'agit d'une statistique de dépistage. De nombreuses associations médicament–événement sont examinées en même temps et la plupart remplissent ces critères ; les remplir est donc courant et ne prouve pas que le médicament provoque l'événement.
- L'absence de signalements, ou un schéma qui n'est pas clair, ne signifie pas qu'il n'y a pas d'association ni que les médicaments du patient sont exempts de problèmes.
- Les chiffres couvrent les signalements reçus ou mis à jour pendant les quatre trimestres 2025Q4–2026Q3, y compris les versions de suivi de cas reçus plus tôt.
- Les chiffres n'utilisent que les signalements qui citent au moins un médicament reconnu par Janus (84,8 % des signalements de cette période). Certaines orthographes ne sont pas reconnues, un schéma peut donc passer inaperçu.
- Source : FDA AEMS (anciennement FAERS), version du 28/10/2026. Ne constitue pas un aval de la FDA.
- MedDRA® the Medical Dictionary for Regulatory Activities terminology is the international medical terminology developed under the auspices of ICH. MedDRA® trademark is registered by IFPMA on behalf of ICH.

### scope

- Janus a vérifié 63 des 65 schémas de cascade de prescription de la liste PIPC.
- La ligne 27 (Inhibiteur de la cholinestérase → Troubles digestifs → Subsalicylate de bismuth) ne peut pas être vérifiée.
- La ligne 57 (Anticholinergique urinaire → Sécheresse buccale → Substitut salivaire) ne peut pas être vérifiée.

### integrity

- Sources utilisées : 4, dont 3 vérifiées par DOI dans les données de rétractation.
- Statut des sources vérifiées : sans avis 2, erratum 1, expression of concern 0, pas encore vérifiées 0.
- Les vérifications de rétractation ont été faites entre le 07/11/2026 et le 07/11/2026.
- Aucune source rétractée n'a été utilisée.

### about

- Versions : règles 8d4881fc, données médicaments 7db3a513, sources 8a5b888f, comptes de signalements 20261108, glossaire 226aaf2e.
- Schémas de cascade de prescription : liste PIPC (Rochon et al., European Geriatric Medicine 2025), sous licence CC BY 4.0.
- Les comptes de signalements proviennent des données trimestrielles publiques de la FDA AEMS (anciennement FAERS).
- Les traductions des termes cliniques ont été revues par le responsable du projet avec l'aide de l'IA ; elles doivent encore être revues par un pharmacien ou un médecin et par des locuteurs natifs.

---

## Español (es)


### header

- Preparada por Janus (11/2026) a partir de los medicamentos introducidos por el paciente o un cuidador.
- Esta nota enumera los patrones publicados de cascada de prescripción que coinciden con los medicamentos del paciente, con sus fuentes. Sirve de apoyo para la conversación con el paciente y no sustituye el juicio clínico.
- Janus ofrece información, no consejo médico. Prototipo de investigación: no es un producto sanitario.

### medicines

- amlodipina [C08CA01]; Inicio: 03/2025
- furosemida [C03CA01]; Inicio: 06/2025
- esomeprazol [A02BC05]; Inicio: 01/2025
- cianocobalamina [B03BA01]; Inicio: 08/2025
- metoclopramida [A03FA01]; Inicio: 02/2025
- haloperidol [N05AD01]; Inicio: 05/2025 — No suspenda este medicamento de forma brusca.
- imipenem [J01DH51] (código de combinación); Fecha de inicio desconocida

### findings

- No hay nada que mostrar en esta sección.

### findings_form_unconfirmed

- En estos medicamentos no se confirmó el producto exacto (por ejemplo, comprimido o colirio), por lo que se tuvieron en cuenta todas las formas del principio activo. Compruebe qué producto usa el paciente.
- Coincidencia con el patrón publicado de cascada de prescripción (Antagonista del calcio → Edema periférico → Diurético; lista PIPC, fila 5): amlodipina y furosemida.
- Meses desde el inicio de amlodipina hasta el inicio de furosemida: 3. Está dentro de la ventana de 12 meses que se usa habitualmente en el análisis de simetría de secuencia de prescripción.
- La misma cascada también se describe en otra lista publicada de cascadas (ThinkCascades).
- Se ha publicado una corrección de una fuente de este patrón.
- Puede ser útil revisar este patrón con el paciente.
- Coincidencia con el patrón publicado de cascada de prescripción (Inhibidor de la bomba de protones → Déficit de vitaminas o minerales → Déficit de vitaminas o minerales; lista PIPC, fila 49): esomeprazol y cianocobalamina.
- Meses desde el inicio de esomeprazol hasta el inicio de cianocobalamina: 7. Está dentro de la ventana de 12 meses que se usa habitualmente en el análisis de simetría de secuencia de prescripción.
- La fila 49 de la lista PIPC nombra el segundo paso tal como se publicó y repite el evento adverso. Para esta fila, Janus comprueba los suplementos de vitamina B12, magnesio y hierro oral.
- Se ha publicado una corrección de una fuente de este patrón.
- Puede ser útil revisar este patrón con el paciente.

### statistics

- Todas las regiones: 424 informes citan amlodipina junto con el evento «Edema periférico»; razón de odds de notificación (ROR) 5,14 (intervalo de confianza de 4,65 a 5,67). El evento aparece en una proporción mayor de los informes que nombran este medicamento que en los demás informes que nombran un medicamento reconocido.
- Unión Europea: 100 informes citan amlodipina junto con el evento «Edema periférico»; razón de odds de notificación (ROR) 5,63 (intervalo de confianza de 4,57 a 6,93). El evento aparece en una proporción mayor de los informes que nombran este medicamento que en los demás informes que nombran un medicamento reconocido.
- Todas las regiones: 147 informes citan esomeprazol junto con el evento «Déficit de vitaminas o minerales»; razón de odds de notificación (ROR) 20,7 (intervalo de confianza de 17,4 a 24,5). El evento aparece en una proporción mayor de los informes que nombran este medicamento que en los demás informes que nombran un medicamento reconocido.
- Unión Europea: 108 informes citan esomeprazol junto con el evento «Déficit de vitaminas o minerales»; razón de odds de notificación (ROR) 21,3 (intervalo de confianza de 17,2 a 26,3). El evento aparece en una proporción mayor de los informes que nombran este medicamento que en los demás informes que nombran un medicamento reconocido.
- Los informes se envían de forma voluntaria y no se verifican.
- Los recuentos no muestran con qué frecuencia ocurre un evento.
- Solo se fusionan las versiones repetidas de un mismo caso, por lo que un mismo evento puede aparecer en más de un caso.
- Es una estadística de cribado. Se examinan a la vez muchas combinaciones de medicamento y evento y la mayoría cumple estos criterios; cumplirlos es habitual y no es una prueba de que el medicamento cause el evento.
- La ausencia de informes, o un patrón poco claro, no significa que no haya asociación ni que los medicamentos del paciente estén libres de problemas.
- Los recuentos cubren los informes recibidos o actualizados en los cuatro trimestres 2025Q4–2026Q3, incluidas las versiones de seguimiento de casos recibidos antes.
- Los recuentos usan solo los informes que nombran al menos un medicamento que Janus reconoce (84,8 % de los informes de este periodo). Algunas grafías no se reconocen, por lo que un patrón puede pasar inadvertido.
- Fuente: FDA AEMS (antes FAERS), versión del 28/10/2026. No es un respaldo de la FDA.
- MedDRA® the Medical Dictionary for Regulatory Activities terminology is the international medical terminology developed under the auspices of ICH. MedDRA® trademark is registered by IFPMA on behalf of ICH.

### scope

- Janus comprobó 63 de los 65 patrones de cascada de prescripción de la lista PIPC.
- La fila 27 (Inhibidor de la colinesterasa → Molestias gastrointestinales → Subsalicilato de bismuto) no se puede comprobar.
- La fila 57 (Anticolinérgico urinario → Sequedad de boca → Sustituto de la saliva) no se puede comprobar.

### integrity

- Fuentes utilizadas: 4, de las cuales 3 se comprobaron por DOI frente a los datos de retractaciones.
- Estado de las fuentes comprobadas: sin aviso 2, corrección 1, expresión de preocupación 0, aún sin comprobar 0.
- Las comprobaciones de retractaciones se hicieron entre el 07/11/2026 y el 07/11/2026.
- No se utilizó ninguna fuente retractada.

### about

- Versiones: reglas 8d4881fc, datos de medicamentos 7db3a513, evidencia 8a5b888f, recuentos de informes 20261108, glosario 226aaf2e.
- Patrones de cascada de prescripción: lista PIPC (Rochon et al., European Geriatric Medicine 2025), con licencia CC BY 4.0.
- Los recuentos de informes proceden de los datos trimestrales públicos de FDA AEMS (antes FAERS).
- Las traducciones de los términos clínicos fueron revisadas por el responsable del proyecto con ayuda de IA; aún deben revisarlas un farmacéutico o un médico y hablantes nativos.
