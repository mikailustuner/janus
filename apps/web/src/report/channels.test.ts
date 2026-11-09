// Feature: report-assistant, the channel table (Req 1, design §3.1, §5 P2, DP2–DP4).
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import {
  findForbiddenPhrases,
  forbiddenPhrases,
} from "@/i18n/forbidden-phrases";

import en from "../../messages/en.json";
import json from "./channels.json";
import {
  CHANNELS,
  contactChannels,
  fieldList,
  formChannels,
  knownUrls,
} from "./channels";
import { parseCsv, toChannels } from "./csv.mjs";
import { LABEL_IDS, MAPPINGS } from "./mapping";

const root = join(import.meta.dirname, "..", "..", "..", "..");
const csvText = readFileSync(join(root, "data", "report_channels.csv"), "utf8");
const rows = parseCsv(csvText).filter((r) => r.some(Boolean));
const header = rows[0]!;
const records = rows
  .slice(1)
  .map((r) => Object.fromEntries(header.map((h, i) => [h, r[i] ?? ""])));

describe("data/report_channels.csv", () => {
  it("has the documented columns and one row per channel id", () => {
    expect(header).toEqual([
      "channel_id",
      "region",
      "country",
      "authority",
      "channel_name",
      "audience",
      "kind",
      "url",
      "form_id",
      "form_version",
      "language",
      "patient_may_report",
      "fields_status",
      "field_source",
      "fields",
      "required_fields",
      "outcome_field",
      "outcome_options",
      "source_url",
      "checked_on",
      "notes",
    ]);
    for (const r of rows.slice(1)) expect(r).toHaveLength(header.length);
    const ids = records.map((r) => r.channel_id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("every row has an https source_url, a checked_on date and an allowed URL", () => {
    for (const r of records) {
      expect(r.source_url, r.channel_id).toMatch(/^https:\/\/[^\s]+$/);
      expect(r.checked_on, r.channel_id).toMatch(/^\d{4}-\d{2}-\d{2}$/);
      expect(Number.isNaN(Date.parse(r.checked_on!))).toBe(false);
      if (r.kind === "email") expect(r.url).toMatch(/^mailto:[^\s@]+@[^\s@]+$/);
      else if (r.kind === "phone") expect(r.url).toMatch(/^tel:\+[0-9]+$/);
      else expect(r.url, r.channel_id).toMatch(/^https:\/\/[^\s]+$/);
    }
  });

  it("uses the verified FDA 3500B and French portal addresses only", () => {
    expect(csvText).not.toMatch(/media\/76299\/download/);
    expect(csvText).not.toMatch(
      /https?:\/\/(www\.)?signalement-sante\.gouv\.fr/,
    );
    const pdf = records.find((r) => r.channel_id === "us-fda-3500b-pdf")!;
    expect(pdf.url).toBe("https://www.fda.gov/media/85598/download?attachment");
    expect(pdf.form_version).toContain("09/2025");
    expect(pdf.form_version).toContain("0910-0291");
    expect(records.find((r) => r.channel_id === "tr-tufam-eform")!.url).toBe(
      "https://vigiflow-eforms.who-umc.org/tr/tr",
    );
  });

  it("allows only known values and says UNVERIFIED instead of guessing", () => {
    for (const r of records) {
      expect(["TR", "EU", "US"]).toContain(r.region);
      expect([
        "verified",
        "derived",
        "partial",
        "unverified",
        "none",
      ]).toContain(r.fields_status);
      expect(r.patient_may_report).toBe("yes");
      if (r.fields_status === "unverified") {
        expect(r.fields).toBe("");
        expect(r.required_fields).toMatch(/UNVERIFIED/);
      }
    }
  });

  it("the shipped JSON is the CSV (regenerate: node scripts/gen-report-channels.mjs)", () => {
    expect(json).toEqual(toChannels(csvText));
  });

  it("holds no MedDRA Preferred Term of the event vocabulary (DP3)", () => {
    const events = parseCsv(
      readFileSync(
        join(root, "apps", "api", "janus", "memory", "memory_events.csv"),
        "utf8",
      ),
    );
    const h = events[0]!;
    const pts = new Set(
      events
        .slice(1)
        .flatMap((r) => (r[h.indexOf("pts")] ?? "").split("|"))
        .filter((p) => p.length > 3),
    );
    for (const c of CHANNELS)
      for (const s of [...c.fields, ...c.outcomeOptions]) {
        const field = s.split(" > ").pop()!;
        expect(pts.has(field), `${c.id}: ${field}`).toBe(false);
      }
  });
});

describe("field mappings (DP4, P1 for the static table)", () => {
  it("every mapped label is in its field list, in form order", () => {
    for (const [id, map] of Object.entries(MAPPINGS)) {
      const c = CHANNELS.find((x) => x.id === id)!;
      expect(c, id).toBeDefined();
      expect(fieldList(c)?.borrowed).toBe(false);
      const idx = map.map((f) => c.fields.indexOf(f.label));
      for (const [k, i] of idx.entries())
        expect(i, `${id}: ${map[k]!.label}`).toBeGreaterThanOrEqual(0);
      expect([...idx].sort((a, b) => a - b)).toEqual(idx);
      expect(new Set(map.map((f) => f.key)).size).toBe(map.length);
    }
  });

  it("only read lists are used: no mapping on page-1-only or unverified forms", () => {
    expect(
      fieldList(CHANNELS.find((c) => c.id === "de-bund-online")!),
    ).toBeNull();
    expect(
      fieldList(CHANNELS.find((c) => c.id === "fr-portail-signalement")!),
    ).toBeNull();
    expect(
      fieldList(CHANNELS.find((c) => c.id === "us-fda-3500b-online")!),
    ).toMatchObject({ borrowed: true });
  });

  it("no label the assistant can show holds a forbidden phrase (medical-safety rule 2)", () => {
    const shown = [
      ...Object.values(MAPPINGS).flatMap((m) => m.map((f) => f.label)),
      ...CHANNELS.flatMap((c) => [...c.required, ...c.outcomeOptions, c.name]),
    ];
    for (const s of shown)
      for (const phrases of Object.values(forbiddenPhrases))
        expect(findForbiddenPhrases(s, phrases), s).toEqual([]);
  });

  it("every translation id has an English text", () => {
    const labels = (
      en as { ReportAssistant: { labels: Record<string, string> } }
    ).ReportAssistant.labels;
    for (const id of LABEL_IDS) expect(labels[id], id).toBeTruthy();
  });
});

describe("channel lists", () => {
  it("each country has a form channel; TR lists its e-mail and phone", () => {
    for (const k of ["TR", "US", "DE", "FR", "ES", "EU"] as const)
      expect(formChannels(k).length, k).toBeGreaterThan(0);
    expect(formChannels("TR")[0]!.id).toBe("tr-tufam-eform");
    expect(contactChannels("TR").map((c) => c.kind)).toEqual([
      "email",
      "phone",
    ]);
  });

  it("P2: every URL comes from the CSV", () => {
    const urls = new Set(records.flatMap((r) => [r.url, r.source_url]));
    expect(knownUrls()).toEqual(urls);
  });
});
