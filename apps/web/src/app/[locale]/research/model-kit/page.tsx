import type { Metadata } from "next";

import { pageMetadata } from "@/seo/metadata";
import { ModelKitList } from "@/components/modelkit/ModelKitList";

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/research/model-kit">): Promise<Metadata> {
  const { locale } = await params;
  return pageMetadata(locale, "modelKit");
}

export default function ModelKitPage() {
  return <ModelKitList />;
}
