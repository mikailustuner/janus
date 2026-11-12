import { noIndex } from "@/seo/metadata";
import { DeleteDonation } from "@/components/donate/DeleteDonation";

export const metadata = noIndex;

export default function Page() {
  return <DeleteDonation />;
}
