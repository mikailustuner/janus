import { noIndex } from "@/seo/metadata";
import { MemoryPage } from "@/components/memory/MemoryPage";

export const metadata = noIndex;

export default function Memory() {
  return <MemoryPage />;
}
