/**
 * `NoteOut` + list → the note layout (experience design §10.1, Req 17.3–17.10, P4, P24). Pure.
 * Sections in `SECTION_ORDER`; every sentence copied verbatim (never re-worded, re-ordered,
 * translated or dropped); each medicine row's product-name slot filled from the box name of the
 * list item with the row's index — the box name never reaches the server. Side by side pairs the
 * blocks of two documents by section id and block id; a missing partner is a contract error.
 */
import type {
  MedicineRow,
  NoteDocument,
  NoteOut,
  Sentence,
  StatRow,
} from "@/api/contracts";
import { ContractError, SECTION_ORDER } from "@/api/decode";

export type LaidBlock =
  | { kind: "sentence"; id: string; text: string }
  | {
      kind: "medicine";
      id: string;
      item: number;
      productLabel: string;
      productName: string | null;
      ingredients: {
        name: string | null;
        key: string;
        tag: string | null;
        atc: string[];
        combinationCode: string | null;
      }[];
      notChecked: string[];
      started: string;
      abruptStop: string | null;
    }
  | {
      kind: "stat";
      id: string;
      sentences: { id: string; text: string }[];
      pts: string | null;
    };

export interface LaidSection {
  id: (typeof SECTION_ORDER)[number];
  heading: string | null;
  blocks: LaidBlock[];
}

export interface LaidDocument {
  language: NoteDocument["language"];
  sections: LaidSection[];
  disclaimer: string | null;
  title: string | null;
}

export interface NoteLayout {
  documents: LaidDocument[];
  asOfMonth: string;
  versions: NoteOut["versions"];
  demo: boolean;
  /** Present when the note has two languages: rows of paired blocks by section and id. */
  sideBySide:
    | {
        section: string;
        heading: [string | null, string | null];
        rows: [LaidBlock, LaidBlock][];
      }[]
    | null;
}

function block(
  b: Sentence | MedicineRow | StatRow,
  boxNames: readonly string[],
): LaidBlock {
  if (b.type === "sentence")
    return { kind: "sentence", id: b.id, text: b.text };
  if (b.type === "medicine")
    return {
      kind: "medicine",
      id: `medicine:${b.item}`,
      item: b.item,
      productLabel: b.product_label.text,
      productName: boxNames[b.item] || null,
      ingredients: b.ingredients.map((i) => ({
        key: i.key,
        name: i.name?.text ?? null,
        tag: i.tag?.text ?? null,
        atc: [...i.atc],
        combinationCode: i.combination_code?.text ?? null,
      })),
      notChecked: b.not_checked.map((n) => n.text.text),
      started: b.started.text,
      abruptStop: b.abrupt_stop?.text ?? null,
    };
  return {
    kind: "stat",
    id: b.id,
    sentences: b.sentences.map((s) => ({ id: s.id, text: s.text })),
    pts: b.pts?.text ?? null,
  };
}

export function layoutDocument(
  doc: NoteDocument,
  boxNames: readonly string[],
): LaidDocument {
  const order = (id: string) =>
    SECTION_ORDER.indexOf(id as (typeof SECTION_ORDER)[number]);
  const sections = [...doc.sections]
    .sort((a, b) => order(a.id) - order(b.id))
    .map((s) => ({
      id: s.id,
      heading: s.heading?.text ?? null,
      blocks: s.blocks.map((b) => block(b, boxNames)),
    }));
  const header = sections.find((s) => s.id === "header");
  const disclaimer =
    sections
      .flatMap((s) => s.blocks)
      .find((b) => b.kind === "sentence" && /(^|:)disclaimer$/.test(b.id)) ??
    null;
  // Rule 9: every page of the note carries the disclaimer; a note without it is a contract error
  // (safety audit A5), never a PDF printed without it.
  if (!disclaimer)
    throw new ContractError(`documents.${doc.language}.disclaimer`);
  return {
    language: doc.language,
    sections,
    disclaimer:
      disclaimer && disclaimer.kind === "sentence" ? disclaimer.text : null,
    title: header?.heading ?? null,
  };
}

export function layout(
  note: NoteOut,
  boxNames: readonly string[],
  demo: boolean,
): NoteLayout {
  const documents = note.documents.map((d) => layoutDocument(d, boxNames));
  let sideBySide: NoteLayout["sideBySide"] = null;
  if (documents.length === 2) {
    const [a, b] = documents as [LaidDocument, LaidDocument];
    if (a.sections.length !== b.sections.length)
      throw new ContractError("documents.sections");
    sideBySide = a.sections.map((sa, i) => {
      const sb = b.sections[i]!;
      if (sa.id !== sb.id || sa.blocks.length !== sb.blocks.length)
        throw new ContractError(`documents.sections.${sa.id}`);
      const byId = new Map(sb.blocks.map((x) => [x.id, x]));
      return {
        section: sa.id,
        heading: [sa.heading, sb.heading],
        rows: sa.blocks.map((x) => {
          const partner = byId.get(x.id);
          if (!partner)
            throw new ContractError(`documents.sections.${sa.id}.${x.id}`);
          return [x, partner] as [LaidBlock, LaidBlock];
        }),
      };
    });
  }
  return {
    documents,
    asOfMonth: note.as_of_month,
    versions: note.versions,
    demo,
    sideBySide,
  };
}

/** `janus-note-<YYYY-MM>.pdf`: no name, no date finer than the month (§10.2). */
export function pdfFileName(asOfMonth: string): string {
  return `janus-note-${asOfMonth}.pdf`;
}

/** Letter for English with user region US, else A4 (§10.2). */
export function paperFor(locale: string, region: string): "A4" | "LETTER" {
  return locale === "en" && region === "US" ? "LETTER" : "A4";
}
