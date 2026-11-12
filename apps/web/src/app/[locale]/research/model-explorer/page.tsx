import type { Metadata } from "next";

import { pageMetadata } from "@/seo/metadata";
import { ModelExplorer } from "@/components/simulation/ModelExplorer";

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/research/model-explorer">): Promise<Metadata> {
  const { locale } = await params;
  return pageMetadata(locale, "modelExplorer");
}

export default function ModelExplorerPage() {
  return <ModelExplorer />;
}
