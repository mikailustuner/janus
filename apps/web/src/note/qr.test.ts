// Feature: experience, Property P25: for any address `<origin ≤ 40 bytes>/o#<token>` within the
// API's bounds, the drawn code has version ≤ 25, level M, byte mode, and decodes (zxing-wasm in
// node) back to the same address; the token occurs only after `#` (Req 18.2, 18.3).
import { describe, expect, it } from "vitest";
import { readBarcodes } from "zxing-wasm/reader";

import { check, fc } from "@/test/fc";

import { makeQr, MAX_VERSION, qrAddress, QUIET } from "./qr";

/** Draws the modules into a grey image (4 px per module) that zxing-wasm reads in node. */
function image(qr: NonNullable<ReturnType<typeof makeQr>>) {
  const scale = 4;
  const side = (qr.size + 2 * QUIET) * scale;
  const data = new Uint8ClampedArray(side * side * 4).fill(255);
  qr.modules.forEach((row, y) =>
    row.forEach((on, x) => {
      if (!on) return;
      for (let dy = 0; dy < scale; dy++)
        for (let dx = 0; dx < scale; dx++) {
          const i =
            (((y + QUIET) * scale + dy) * side + (x + QUIET) * scale + dx) * 4;
          data[i] = data[i + 1] = data[i + 2] = 0;
        }
    }),
  );
  return {
    data,
    width: side,
    height: side,
    colorSpace: "srgb",
  } as unknown as ImageData;
}

// The longest token whose address with a 40-byte origin still fits version 25 at level M.
let maxToken = 40;
while (makeQr(`https://${"a".repeat(32)}/o#${"A".repeat(maxToken + 1)}`))
  maxToken++;

const origin = fc
  .stringMatching(/^[a-z0-9-]{1,32}$/)
  .map((h) => `https://${h}`)
  .filter((o) => new TextEncoder().encode(o).length <= 40);
const token = fc
  .integer({ min: 40, max: maxToken })
  .chain((n) => fc.stringMatching(new RegExp(`^[A-Za-z0-9_-]{${n}}$`)));

describe("P25 QR", () => {
  it("fits version 25 for the API's longest address and decodes back", async () => {
    expect(maxToken).toBeGreaterThan(200);
    await check(
      fc.asyncProperty(origin, token, async (o, t) => {
        const address = qrAddress(null, o, t);
        expect(address.indexOf(t)).toBe(address.indexOf("#") + 1);
        const qr = makeQr(address);
        expect(qr).not.toBeNull();
        expect(qr!.version).toBeLessThanOrEqual(MAX_VERSION);
        const [r] = await readBarcodes(image(qr!), { formats: ["QRCode"] });
        expect(r?.text).toBe(address);
        expect(r?.ecLevel).toBe("M");
      }),
      { numRuns: 25 },
    );
  });
  it("refuses an address past version 25 and prefers the API's qr_url", () => {
    expect(makeQr(`https://x/o#${"A".repeat(maxToken + 200)}`)).toBeNull();
    expect(qrAddress("https://janus.example/o#T", "https://other", "T")).toBe(
      "https://janus.example/o#T",
    );
  });
});
