/**
 * Lazy barcode reader (experience design §6.1, DP9): zxing-wasm's reader build, its wasm served
 * from /vendor/zxing on the Janus origin. Images and frames stay in memory and are released after
 * decoding; the decoded text goes only to `gs1.ts`.
 */
import type { ReadResult } from "zxing-wasm/reader";

const FORMATS = ["DataMatrix", "EAN-13", "EAN-8", "UPC-A", "Code128"] as const;

let ready: Promise<typeof import("zxing-wasm/reader")> | null = null;

function reader() {
  if (!ready)
    ready = import("zxing-wasm/reader").then((m) => {
      m.prepareZXingModule({
        overrides: {
          locateFile: (path: string, prefix: string) =>
            path.endsWith(".wasm")
              ? "/vendor/zxing/zxing_reader.wasm"
              : prefix + path,
        },
        fireImmediately: true,
      });
      return m;
    });
  return ready;
}

export async function decode(image: ImageData | Blob): Promise<string | null> {
  const m = await reader();
  const results: ReadResult[] = await m.readBarcodes(image, {
    formats: [...FORMATS],
    tryHarder: true,
    maxNumberOfSymbols: 1,
  });
  const hit = results.find((r) => r.isValid && r.text);
  return hit ? hit.text : null;
}
