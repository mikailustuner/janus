import { noIndex } from "@/seo/metadata";
import { FindingDetail } from "@/components/results/FindingDetail";

export const metadata = noIndex;

export default function FindingPage() {
  return <FindingDetail />;
}
