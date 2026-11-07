import { notFound } from "next/navigation";

// Sends unknown paths under a valid locale to the localized not-found page.
export default function CatchAllPage() {
  notFound();
}
