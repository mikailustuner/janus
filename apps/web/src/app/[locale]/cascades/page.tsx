import type { Metadata } from "next";

import { pageMetadata } from "@/seo/metadata";
import { CascadeMap } from "@/components/cascade-map/CascadeMap";

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/cascades">): Promise<Metadata> {
  const { locale } = await params;
  return pageMetadata(locale, "cascades");
}

export default function CascadesPage() {
  return <CascadeMap />;
}
