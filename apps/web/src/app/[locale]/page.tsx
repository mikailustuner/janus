import { Home } from "@/components/home/Home";
import { scenePreloadScript } from "@/components/home/ScenePicture";

export default function HomePage() {
  return (
    <>
      {/* Preloads only the active theme's hero image, before the parser reaches it (DP46). */}
      <script dangerouslySetInnerHTML={{ __html: scenePreloadScript() }} />
      <Home />
    </>
  );
}
