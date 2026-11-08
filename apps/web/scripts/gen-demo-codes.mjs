/**
 * Draws the demo sheet's GS1 DataMatrix codes (experience design §13.2) as SVG with zxing-wasm's
 * writer, in node, and writes src/demo/codes.svg.json. Each code carries (01) the demo GTIN,
 * (17) an expiry and, on purpose, (21) a serial number that Janus never sends.
 *
 *   node apps/web/scripts/gen-demo-codes.mjs
 */
import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import { writeBarcode } from "zxing-wasm/writer";

const PATIENTS = [
  ["istanbul", 0, 9],
  ["cologne", 10, 4],
  ["ohio", 20, 4],
];
export const EXPIRY = "281231";

export function checkDigit(body) {
  let sum = 0;
  for (let i = 0; i < body.length; i++)
    sum += Number(body[body.length - 1 - i]) * (i % 2 === 0 ? 3 : 1);
  return String((10 - (sum % 10)) % 10);
}

export function elementString(gtin13, serial) {
  return `(01)0${gtin13}(17)${EXPIRY}(21)DEMO${serial}`;
}

const here = fileURLToPath(new URL(".", import.meta.url));
const out = {};
for (const [patient, offset, count] of PATIENTS) {
  const fixture = JSON.parse(
    readFileSync(join(here, `../src/demo/fixtures/${patient}.json`), "utf8"),
  );
  for (let i = 0; i < count; i++) {
    const body = "295268" + String(offset + i + 1).padStart(6, "0");
    const gtin13 = body + checkDigit(body);
    const text = elementString(gtin13, String(offset + i + 1).padStart(3, "0"));
    const r = await writeBarcode(text, {
      format: "DataMatrix",
      options: "gs1",
      scale: 1,
    });
    if (r.error) throw new Error(r.error);
    // A viewBox so the symbol scales in an <img>, and crisp module edges.
    const svg = r.svg
      .slice(r.svg.indexOf("<svg"))
      .replace(
        /<svg width="(\d+)" height="(\d+)"/,
        '<svg viewBox="0 0 $1 $2" width="$1" height="$2" shape-rendering="crispEdges"',
      );
    const item = fixture.items[i];
    if (item.demoCode !== gtin13)
      throw new Error(`fixture ${patient} item ${i} has another demo code`);
    const ndc = item.sourceKey.kind === "ndc" ? item.sourceKey.ndc : null;
    out[gtin13] = { patient, index: i, text, boxName: item.boxName, ndc, svg };
  }
}
writeFileSync(
  join(here, "../src/demo/codes.svg.json"),
  JSON.stringify(out, null, 1) + "\n",
);
console.log(`${Object.keys(out).length} demo codes written`);
