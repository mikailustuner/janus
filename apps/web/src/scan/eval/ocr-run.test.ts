/**
 * Reads the synthetic label images with the same recogniser, models and options as the app and
 * records the text (ocr-first Req 5). Slow, and it needs the images of
 * `scripts/ocr-eval-fixtures.mjs` and the vendored models, so it only runs on request:
 *
 *   node scripts/ocr-eval-fixtures.mjs
 *   OCR_EVAL=1 pnpm vitest --run src/scan/eval/ocr-run.test.ts
 *
 * It writes `ocr-text.json` next to this file; `hit-rate.test.ts` measures matching on it.
 */
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

import { chromium } from "@playwright/test";
import { describe, expect, it } from "vitest";

import { RETRY_BELOW, type Turns } from "../ocr-passes";

import type { EvalCase, Recorded } from "./measure";

const dir = join(import.meta.dirname, "../../../.ocr-eval");
const lang = join(import.meta.dirname, "../../../public/vendor/tesseract/lang");
const LANG = { en: "eng", tr: "tur", de: "deu", fr: "fra", es: "spa" } as const;

describe.skipIf(!process.env.OCR_EVAL)("label images → recognised text", () => {
  it("records every reading the app could make", async () => {
    expect(
      existsSync(join(dir, "cases.json")),
      "run ocr-eval-fixtures.mjs",
    ).toBe(true);
    const cases = JSON.parse(
      readFileSync(join(dir, "cases.json"), "utf8"),
    ) as (EvalCase & { file: string })[];
    const { createWorker } = await import("tesseract.js");
    const browser = await chromium.launch();
    const page = await browser.newPage();
    // The same canvas turn as `scan/ocr.ts`.
    const turn = (png: Buffer, turns: Turns) =>
      page
        .evaluate(
          async ({ b64, turns }) => {
            const blob = await (
              await fetch(`data:application/octet-stream;base64,${b64}`)
            ).blob();
            const bmp = await createImageBitmap(blob);
            const odd = turns % 2 === 1;
            const c = document.createElement("canvas");
            c.width = odd ? bmp.height : bmp.width;
            c.height = odd ? bmp.width : bmp.height;
            const ctx = c.getContext("2d")!;
            ctx.translate(c.width / 2, c.height / 2);
            ctx.rotate((turns * Math.PI) / 2);
            ctx.drawImage(bmp, -bmp.width / 2, -bmp.height / 2);
            return c.toDataURL("image/png").split(",")[1]!;
          },
          { b64: png.toString("base64"), turns },
        )
        .then((b64) => Buffer.from(b64, "base64"));

    const out: Recorded[] = [];
    for (const locale of ["en", "tr", "de", "fr", "es"] as const) {
      const langs = locale === "en" ? ["eng"] : [LANG[locale], "eng"];
      const worker = await createWorker(langs, 1, {
        langPath: lang,
        gzip: false,
        cacheMethod: "none",
      });
      const read = async (png: Buffer, rotateAuto: boolean) => {
        const { data } = await worker.recognize(
          png,
          rotateAuto ? { rotateAuto: true } : {},
          { blocks: true },
        );
        const lines: string[] = [];
        for (const b of data.blocks ?? [])
          for (const p of b.paragraphs)
            for (const l of p.lines)
              if (l.text.trim()) lines.push(l.text.trim());
        return { confidence: Math.round(data.confidence), lines };
      };
      for (const c of cases.filter((x) => x.locale === locale)) {
        const png = readFileSync(join(dir, c.file));
        const before = await read(png, false);
        const upright = await read(png, true);
        const passes: Recorded["passes"] = { 0: upright };
        if (upright.confidence < RETRY_BELOW + 10)
          for (const t of [1, 2, 3] as const)
            passes[t] = await read(await turn(png, t), true);
        const { file, ...rest } = c;
        void file;
        out.push({ ...rest, before, passes });
      }
      await worker.terminate();
    }
    await browser.close();
    out.sort((a, b) => a.id.localeCompare(b.id));
    writeFileSync(
      join(import.meta.dirname, "ocr-text.json"),
      JSON.stringify(out, null, 1) + "\n",
    );
    expect(out).toHaveLength(cases.length);
  }, 3_600_000);
});
