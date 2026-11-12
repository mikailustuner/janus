import type { Metadata } from "next";

import { About } from "@/components/about/About";
import { pageMetadata } from "@/seo/metadata";

export async function generateMetadata({
  params,
}: PageProps<"/[locale]/about">): Promise<Metadata> {
  const { locale } = await params;
  return pageMetadata(locale, "about");
}

export default function AboutPage() {
  return <About />;
}
