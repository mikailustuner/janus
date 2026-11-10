/**
 * The Cologne demo list's product lists (medication-passport design §15, DP33): the first page per
 * target source, recorded from the real API (`scripts/record-passport-products.mjs`). Product
 * names come from the open-licence sources only (BDPM, AEMPS Nomenclátor, openFDA NDC), as
 * published, with the data dates inside each answer. Demo mode shows only these.
 */
import type { RecordedProducts } from "@/passport/products";

import recorded from "./passport-products.recorded.json";

export const COLOGNE_PRODUCTS = recorded as unknown as RecordedProducts;
