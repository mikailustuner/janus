import type { Metadata } from "next";

import { pageMetadata } from "@/seo/metadata";
import { OpenData } from "@/components/open/OpenData";

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/open-data">): Promise<Metadata> {
  const { locale } = await params;
  return pageMetadata(locale, "openData");
}

export default function OpenDataPage() {
  return <OpenData />;
}
