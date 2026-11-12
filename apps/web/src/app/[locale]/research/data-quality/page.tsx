import type { Metadata } from "next";

import { pageMetadata } from "@/seo/metadata";
import { DataQuality } from "@/components/research/DataQuality";

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/research/data-quality">): Promise<Metadata> {
  const { locale } = await params;
  return pageMetadata(locale, "dataQuality");
}

export default function DataQualityPage() {
  return <DataQuality />;
}
