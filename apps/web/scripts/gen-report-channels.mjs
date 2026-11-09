// data/report_channels.csv → src/report/channels.json (report-assistant DP2). The parser is the one
// the tests use (src/report/csv.mjs); `channels.test.ts` fails
// when the committed JSON differs from the CSV.
import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

import { toChannels } from "../src/report/csv.mjs";

const root = join(import.meta.dirname, "..", "..", "..");
const csv = readFileSync(join(root, "data", "report_channels.csv"), "utf8");
const out = join(import.meta.dirname, "..", "src", "report", "channels.json");
writeFileSync(out, JSON.stringify(toChannels(csv), null, 1) + "\n");
console.log(`wrote ${out}`);
