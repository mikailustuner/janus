/**
 * `data/report_channels.csv` → channel records (report-assistant design §3.1, DP2). Pure JS so the
 * generator script and the tests share it; the shipped JSON is the CSV.
 */
/** RFC 4180 rows: quoted fields, doubled quotes, `\n` or `\r\n` line ends. */
/** @param {string} text @returns {string[][]} */
export function parseCsv(text) {
  /** @type {string[][]} */
  const rows = [];
  /** @type {string[]} */
  let row = [];
  let cell = "";
  let quoted = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (quoted) {
      if (c === '"' && text[i + 1] === '"') {
        cell += '"';
        i++;
      } else if (c === '"') quoted = false;
      else cell += c;
    } else if (c === '"') quoted = true;
    else if (c === ",") {
      row.push(cell);
      cell = "";
    } else if (c === "\n" || c === "\r") {
      if (c === "\r" && text[i + 1] === "\n") i++;
      row.push(cell);
      rows.push(row);
      row = [];
      cell = "";
    } else cell += c;
  }
  if (cell !== "" || row.length > 0) {
    row.push(cell);
    rows.push(row);
  }
  return rows;
}

/** @param {string} s */
const list = (s) =>
  s
    .split(";")
    .map((x) => x.trim())
    .filter(Boolean);

/** Fields of the "fields"/"required" columns are free text when the column is a note. */
/** @param {string} s */
const fieldList = (s) =>
  /^(none|n\/a|UNVERIFIED|FAQ minimum)/.test(s) ? [] : list(s);

/** @param {string} text @returns {import("./types").Channel[]} */
export function toChannels(text) {
  const [header, ...rows] = parseCsv(text).filter((r) => r.some(Boolean));
  if (!header) return [];
  return rows.map((r) => {
    const o = Object.fromEntries(header.map((h, i) => [h, r[i] ?? ""]));
    return {
      id: o.channel_id,
      region: o.region,
      country: o.country,
      authority: o.authority,
      name: o.channel_name,
      audience: list(o.audience),
      kind: o.kind,
      url: o.url,
      formId: o.form_id,
      formVersion: o.form_version,
      languages: list(o.language),
      patientMayReport: o.patient_may_report === "yes",
      fieldsStatus: o.fields_status,
      fieldSource: o.field_source || null,
      fields: fieldList(o.fields),
      required: fieldList(o.required_fields),
      outcomeField: o.outcome_field || null,
      outcomeOptions: list(o.outcome_options),
      sourceUrl: o.source_url,
      checkedOn: o.checked_on,
      notes: o.notes,
    };
  });
}
