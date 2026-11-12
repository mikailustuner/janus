import type { Metadata } from "next";

import { pageMetadata } from "@/seo/metadata";
import { Home } from "@/components/home/Home";
import { scenePreloadScript } from "@/components/home/ScenePicture";

export async function generateMetadata({
  params,
}: PageProps<"/[locale]">): Promise<Metadata> {
  const { locale } = await params;
  return pageMetadata(locale, "home");
}

export default function HomePage() {
  return (
    <>
      {/* Preloads only the active theme's hero image, before the parser reaches it (DP46). */}
      <script dangerouslySetInnerHTML={{ __html: scenePreloadScript() }} />
      <Home />
    </>
  );
}
