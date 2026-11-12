import { noIndex } from "@/seo/metadata";
import { ProductsView } from "@/passport/screens/ProductsView";

export const metadata = noIndex;

export default function PassportProductsPage() {
  return <ProductsView />;
}
