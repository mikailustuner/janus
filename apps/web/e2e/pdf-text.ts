/**
 * Extracts the text of a PDF made by @react-pdf/renderer (pdfkit), for the C6 check: inflates
 * the streams, reads each font's ToUnicode CMap and decodes the hex glyph strings of the page
 * content streams with the font selected by `Tf`. Enough for pdfkit output; not a PDF parser.
 */
import { inflateSync } from "node:zlib";

interface Obj {
  dict: string;
  stream: Buffer | null;
}

function objects(pdf: Buffer): Map<number, Obj> {
  const out = new Map<number, Obj>();
  const text = pdf.toString("latin1");
  const re = /(\d+) 0 obj\s*([\s\S]*?)endobj/g;
  for (let m = re.exec(text); m; m = re.exec(text)) {
    const body = m[2]!;
    const si = body.indexOf("stream");
    if (si < 0) {
      out.set(Number(m[1]), { dict: body, stream: null });
      continue;
    }
    const dict = body.slice(0, si);
    let start = m.index + m[0].indexOf(body) + si + "stream".length;
    if (text[start] === "\r") start++;
    if (text[start] === "\n") start++;
    const end = text.indexOf("endstream", start);
    let raw = pdf.subarray(start, end);
    if (/FlateDecode/.test(dict)) {
      try {
        raw = inflateSync(raw);
      } catch {
        raw = inflateSync(raw.subarray(0, raw.length - 1));
      }
    }
    out.set(Number(m[1]), { dict, stream: raw });
  }
  return out;
}

function cmap(s: string): Map<number, string> {
  const map = new Map<number, string>();
  const hex = (h: string) =>
    String.fromCodePoint(
      ...(h.match(/.{4}/g) ?? []).map((x) => parseInt(x, 16)),
    );
  for (const block of s.matchAll(/beginbfchar([\s\S]*?)endbfchar/g))
    for (const p of block[1]!.matchAll(/<([0-9a-fA-F]+)>\s*<([0-9a-fA-F]+)>/g))
      map.set(parseInt(p[1]!, 16), hex(p[2]!));
  for (const block of s.matchAll(/beginbfrange([\s\S]*?)endbfrange/g))
    for (const p of block[1]!.matchAll(
      /<([0-9a-fA-F]+)>\s*<([0-9a-fA-F]+)>\s*(\[[^\]]*\]|<[0-9a-fA-F]+>)/g,
    )) {
      const [lo, hi] = [parseInt(p[1]!, 16), parseInt(p[2]!, 16)];
      if (p[3]!.startsWith("[")) {
        const list = [...p[3]!.matchAll(/<([0-9a-fA-F]+)>/g)].map((x) =>
          hex(x[1]!),
        );
        for (let c = lo; c <= hi; c++) map.set(c, list[c - lo] ?? "");
      } else {
        const base = parseInt(p[3]!.slice(1, -1), 16);
        for (let c = lo; c <= hi; c++)
          map.set(c, String.fromCodePoint(base + c - lo));
      }
    }
  return map;
}

export function pdfText(pdf: Buffer): { text: string; pages: number } {
  const objs = objects(pdf);
  const fontMaps = new Map<number, Map<number, string>>();
  for (const [n, o] of objs) {
    const tu = /\/ToUnicode (\d+) 0 R/.exec(o.dict);
    if (tu)
      fontMaps.set(
        n,
        cmap(objs.get(Number(tu[1]))?.stream?.toString("latin1") ?? ""),
      );
  }
  let text = "";
  let pages = 0;
  for (const [, o] of objs) {
    if (!/\/Type \/Page\b/.test(o.dict)) continue;
    pages++;
    const resRef = /\/Resources (\d+) 0 R/.exec(o.dict);
    const res = resRef ? (objs.get(Number(resRef[1]))?.dict ?? "") : o.dict;
    const fonts = new Map<string, number>();
    const fontDict = /\/Font\s*<<([\s\S]*?)>>/.exec(res)?.[1] ?? "";
    for (const f of fontDict.matchAll(/\/(\w+) (\d+) 0 R/g))
      fonts.set(f[1]!, Number(f[2]));
    const contents = [
      ...(/\/Contents\s*(\[[^\]]*\]|\d+ 0 R)/.exec(o.dict)?.[1] ?? "").matchAll(
        /(\d+) 0 R/g,
      ),
    ].map((x) => Number(x[1]));
    for (const c of contents) {
      const s = objs.get(c)?.stream?.toString("latin1") ?? "";
      let map = new Map<number, string>();
      for (const tok of s.matchAll(
        /\/(\w+)\s+[\d.]+\s+Tf|<([0-9a-fA-F]*)>|(TJ|Tj|T\*|Td|ET)/g,
      )) {
        if (tok[1]) map = fontMaps.get(fonts.get(tok[1]) ?? -1) ?? new Map();
        else if (tok[2] !== undefined)
          for (const g of tok[2].match(/.{4}/g) ?? [])
            text += map.get(parseInt(g, 16)) ?? "";
        else if (tok[3] === "ET" || tok[3] === "Td") text += " ";
      }
    }
    text += "\n";
  }
  return { text: text.replace(/\s+/g, " "), pages };
}
