import { notFound } from "next/navigation";

import { noIndex } from "@/seo/metadata";

export const metadata = noIndex;

// Sends unknown paths under a valid locale to the localized not-found page.
export default function CatchAllPage() {
  notFound();
}
