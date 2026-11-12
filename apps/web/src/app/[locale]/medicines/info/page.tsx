import { noIndex } from "@/seo/metadata";
import { MedicineInfoView } from "@/components/plaininfo/MedicineInfo";

export const metadata = noIndex;

export default function MedicineInfoPage() {
  return <MedicineInfoView />;
}
