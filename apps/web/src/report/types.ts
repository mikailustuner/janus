/** Channel records of `data/report_channels.csv` (report-assistant design §3.1). */
export type Region = "TR" | "EU" | "US";
export type Country = "TR" | "US" | "EU" | "DE" | "FR" | "ES";
export type Kind =
  "online" | "pdf" | "document" | "email" | "phone" | "guidance" | "directory";
export type FieldsStatus =
  "verified" | "derived" | "partial" | "unverified" | "none";

export interface Channel {
  id: string;
  region: Region;
  country: Country;
  authority: string;
  name: string;
  audience: string[];
  kind: Kind;
  url: string;
  formId: string;
  formVersion: string;
  languages: string[];
  patientMayReport: boolean;
  fieldsStatus: FieldsStatus;
  fieldSource: string | null;
  fields: string[];
  required: string[];
  outcomeField: string | null;
  outcomeOptions: string[];
  sourceUrl: string;
  checkedOn: string;
  notes: string;
}
