/**
 * Copies the barcode reader wasm and the OCR worker and core into public/vendor/, and fetches
 * the tessdata_fast language models with pinned SHA-256 (experience design §6.1, §6.4, DP9).
 * Served from the Janus origin (Req 23.4); not committed (.gitignore). Runs before `next build`
 * and `next dev`; a model already present with the right hash is not fetched again.
 *
 *   node apps/web/scripts/vendor-assets.mjs
 */
import { createHash } from "node:crypto";
import {
  copyFileSync,
  existsSync,
  mkdirSync,
  readFileSync,
  writeFileSync,
} from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const out = join(here, "../public/vendor");
const require = createRequire(import.meta.url);

// tessdata_fast, commit 87416418 (2024-08-01), Apache-2.0.
const TESSDATA =
  "https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/87416418657359cb625c412a48b6e1d6d41c29bd";
export const MODELS = {
  eng: "7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2",
  tur: "7393381111e1152420fc4092cb44eef4237580d21b92bf30d7d221aad192c6b7",
  deu: "19d219bbb6672c869d20a9636c6816a81eb9a71796cb93ebe0cb1530e2cdb22d",
  fra: "ced037562e8c80c13122dece28dd477d399af80911a28791a66a63ac1e3445ca",
  spa: "6f2e04d02774a18f01bed44b1111f2cd7f3ba7ac9dc4373cd3f898a40ea6b464",
};

const sha256 = (buf) => createHash("sha256").update(buf).digest("hex");

function copy(from, toDir, name) {
  mkdirSync(toDir, { recursive: true });
  copyFileSync(from, join(toDir, name));
}

// zxing-wasm reader
const zxingWasm = require.resolve("zxing-wasm/reader/zxing_reader.wasm");
copy(zxingWasm, join(out, "zxing"), "zxing_reader.wasm");

// tesseract.js worker and core (tesseract.js-core is a dependency of tesseract.js)
const tessDist = join(dirname(require.resolve("tesseract.js")), "../dist");
copy(join(tessDist, "worker.min.js"), join(out, "tesseract"), "worker.min.js");
const coreDir = dirname(
  createRequire(require.resolve("tesseract.js")).resolve(
    "tesseract.js-core/package.json",
  ),
);
for (const f of [
  "tesseract-core-lstm.wasm.js",
  "tesseract-core-simd-lstm.wasm.js",
  "tesseract-core-relaxedsimd-lstm.wasm.js",
])
  copy(join(coreDir, f), join(out, "tesseract/core"), f);

// language models, hash-checked
const langDir = join(out, "tesseract/lang");
mkdirSync(langDir, { recursive: true });
for (const [lang, hash] of Object.entries(MODELS)) {
  const file = join(langDir, `${lang}.traineddata`);
  if (existsSync(file) && sha256(readFileSync(file)) === hash) continue;
  const res = await fetch(`${TESSDATA}/${lang}.traineddata`, {
    signal: AbortSignal.timeout(120_000),
  });
  if (!res.ok) throw new Error(`tessdata ${lang}: HTTP ${res.status}`);
  const buf = Buffer.from(await res.arrayBuffer());
  if (sha256(buf) !== hash)
    throw new Error(
      `tessdata ${lang}: SHA-256 does not match the pinned value`,
    );
  writeFileSync(file, buf);
}
console.log("vendor assets ready");
