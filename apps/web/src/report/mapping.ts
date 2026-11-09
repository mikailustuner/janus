/**
 * Field mappings (report-assistant design §3.2, DP4–DP6): for each verified field list, which
 * native label (as published, "Section > Label") takes which draft value, in form order. A test
 * checks that every label is in its CSV field list and that the order follows the list.
 * `id` names the translation `ReportAssistant.labels.<id>`.
 */
export type DraftKey =
  "event" | "onset" | "outcome" | "medicine" | "others" | "othersOtc";

/**
 * `othersOtc` holds the other medicines the resolver knows are sold without a prescription; it
 * exists only where a form asks for them apart (3500B E10, DP13). Elsewhere they stay in `others`.
 */
export const DRAFT_KEYS: readonly DraftKey[] = [
  "medicine",
  "event",
  "onset",
  "outcome",
  "othersOtc",
  "others",
];

export interface FieldMap {
  key: DraftKey;
  label: string;
  id: string;
}

const TR_R = "Reaksiyonlar/belirtiler > ";
const TR_2 = "2 Yan etki hakkındaki bilgiler > ";
const TR_3 = "3 Yan etkiye yol açtığından şüphe edilen ilaç > ";
const ES_4 = "4 Datos reacción(es) > ";

export const MAPPINGS: Record<string, readonly FieldMap[]> = {
  "tr-tufam-eform": [
    { key: "event", label: `${TR_R}Reaksiyon/belirti`, id: "trReaction" },
    { key: "onset", label: `${TR_R}Başlangıç tarihi`, id: "trReactionStart" },
    { key: "outcome", label: `${TR_R}Sonuç`, id: "trOutcome" },
    { key: "medicine", label: "İlaçlar > İlaç adı", id: "trDrugName" },
    { key: "others", label: "İlaçlar > İlaç adı", id: "trDrugName" },
  ],
  "tr-tufam-docx": [
    {
      key: "event",
      label: `${TR_2}Yaşanan yan etkiyi ve nasıl meydana geldiğini tanımlayın`,
      id: "trDocxDescribe",
    },
    { key: "onset", label: `${TR_2}Ne zaman başladı?`, id: "trDocxWhen" },
    {
      key: "outcome",
      label: `${TR_2}Yan etkiyi yaşayan kişinin şimdiki durumu nasıl?`,
      id: "trDocxState",
    },
    { key: "medicine", label: `${TR_3}İlacın Adı`, id: "trDocxDrug" },
    { key: "others", label: `${TR_3}Diğer ilacın adı`, id: "trDocxOther" },
  ],
  "us-fda-3500b-pdf": [
    { key: "onset", label: "A3 Date the problem occurred", id: "usA3" },
    {
      key: "event",
      label: "A4 Tell us what happened, how it happened or why it happened",
      id: "usA4",
    },
    {
      key: "medicine",
      label:
        "C1 Name(s) of the product as it appears on the box, bottle, or package",
      id: "usC1",
    },
    {
      key: "othersOtc",
      label:
        "E10 List all over-the-counter medications and any vitamins, minerals, supplements, and herbal remedies being used",
      id: "usE10",
    },
    {
      key: "others",
      label:
        "E11 List all current prescription medications and medical devices being used",
      id: "usE11",
    },
  ],
  "eu-ema-guidance": [
    { key: "medicine", label: "Medicine", id: "emaMedicine" },
    { key: "onset", label: "Onset of side effect", id: "emaOnset" },
    { key: "outcome", label: "Is it ongoing?", id: "emaOngoing" },
    { key: "others", label: "Other medicines", id: "emaOthers" },
  ],
  "de-bfarm-pdf": [
    {
      key: "medicine",
      label: "Verdächtigte(s) Arzneimittel > Bezeichnung o. PZN",
      id: "deDrug",
    },
    { key: "others", label: "Weitere(s) Arzneimittel", id: "deOthers" },
    {
      key: "onset",
      label: "Beschreibung > Startdatum der Nebenwirkung",
      id: "deOnset",
    },
    {
      key: "event",
      label:
        "Beschreibung > Beschreibung des Arzneimittelrisikos / der Nebenwirkung",
      id: "deDescribe",
    },
    {
      key: "outcome",
      label: "Beschreibung > Ausgang der Nebenwirkung",
      id: "deOutcome",
    },
  ],
  "fr-ansm-cerfa-10011": [
    { key: "medicine", label: "Médicament", id: "frDrug" },
    { key: "others", label: "Médicament", id: "frDrug" },
    { key: "onset", label: "Effet > Date de survenue", id: "frOnset" },
    {
      key: "event",
      label: "Effet > Nature et description de l'effet",
      id: "frDescribe",
    },
    { key: "outcome", label: "Evolution", id: "frOutcome" },
  ],
  "es-notificaram-ciudadano": [
    {
      key: "medicine",
      label: "2 Datos medicamento(s) > Nombre del medicamento",
      id: "esDrug",
    },
    {
      key: "others",
      label: "3 Datos otros medicamentos > Nombre del medicamento",
      id: "esOtherDrug",
    },
    {
      key: "event",
      label: `${ES_4}Síntomas de la reacción adversa`,
      id: "esSymptoms",
    },
    {
      key: "onset",
      label: `${ES_4}¿Cuándo han empezado esos síntomas?`,
      id: "esOnset",
    },
    {
      key: "outcome",
      label: `${ES_4}¿Cuál es el estado actual de la persona afectada?`,
      id: "esState",
    },
  ],
};

/** Every translation id used by the mappings (for the message-key test). */
export const LABEL_IDS = [
  ...new Set(Object.values(MAPPINGS).flatMap((m) => m.map((f) => f.id))),
];
