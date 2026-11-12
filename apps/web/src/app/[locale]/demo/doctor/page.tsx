import { noIndex } from "@/seo/metadata";
import { DemoDoctor } from "@/components/demo/DemoDoctor";

export const metadata = noIndex;

export default function Page() {
  return <DemoDoctor />;
}
