import type { Metadata } from "next";

import { pageMetadata } from "@/seo/metadata";
import { DemoPicker } from "@/components/demo/DemoPicker";

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/demo">): Promise<Metadata> {
  const { locale } = await params;
  return pageMetadata(locale, "demo");
}

export default function DemoPage() {
  return <DemoPicker />;
}
