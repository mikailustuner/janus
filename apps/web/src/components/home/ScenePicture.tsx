/**
 * A home scene image in AVIF, WebP and JPEG at 2752, 1600 and 960 px (public/home, README there).
 * Every scene is lazy, so the hidden theme's images are never fetched (both themes' heroes are in
 * the server markup). The active theme's first image is the page's largest paint: it is fetched
 * at once by `scenePreloadScript` and keeps a high fetch priority. (Loading it eagerly was tried in
 * 0.2.0: the largest paint did not move, and the hidden theme's image was fetched too.)
 */
export type SceneName = "night-diorama" | "night-cabinet" | "clinical-hero";

/** The box is at least the viewport, and 1.79 viewport heights wide on tall screens. */
export const SCENE_SIZES = "max(100vw, 179vh)";
/** The Clinical White hero is the window's width at its own ratio, never cropped (DP68). */
export const CLINICAL_SIZES = "100vw";

const sizesFor = (name: SceneName) =>
  name === "clinical-hero" ? CLINICAL_SIZES : SCENE_SIZES;

export function sceneSrcSet(name: SceneName, ext: "avif" | "webp" | "jpg") {
  const widths = ext === "jpg" ? [1600, 960] : [2752, 1600, 960];
  return widths.map((w) => `/home/${name}-${w}.${ext} ${w}w`).join(", ");
}

export function ScenePicture({
  name,
  alt,
  className = "",
  first = false,
}: {
  name: SceneName;
  alt: string;
  className?: string;
  /** The theme's first scene, i.e. the largest paint of the page. */
  first?: boolean;
}) {
  return (
    <picture className={className}>
      <source
        type="image/avif"
        srcSet={sceneSrcSet(name, "avif")}
        sizes={sizesFor(name)}
      />
      <source
        type="image/webp"
        srcSet={sceneSrcSet(name, "webp")}
        sizes={sizesFor(name)}
      />
      <img
        src={`/home/${name}-1600.jpg`}
        srcSet={sceneSrcSet(name, "jpg")}
        sizes={sizesFor(name)}
        alt={alt}
        width={2752}
        height={1536}
        loading="lazy"
        fetchPriority={first ? "high" : "auto"}
        decoding="async"
      />
    </picture>
  );
}

/**
 * Inline script, placed before the heroes: reads the theme the pre-paint script set on <html>
 * and preloads only that theme's first image (AVIF, the browser picks the width), so the LCP
 * image starts at once and the hidden theme's image is never fetched.
 */
export function scenePreloadScript(): string {
  const night = JSON.stringify(sceneSrcSet("night-diorama", "avif"));
  const glass = JSON.stringify(sceneSrcSet("clinical-hero", "avif"));
  return `(function(){try{var g=document.documentElement.getAttribute("data-theme-style")==="glass";var l=document.createElement("link");l.rel="preload";l.as="image";l.type="image/avif";l.setAttribute("imagesrcset",g?${glass}:${night});l.setAttribute("imagesizes",g?${JSON.stringify(CLINICAL_SIZES)}:${JSON.stringify(SCENE_SIZES)});l.setAttribute("fetchpriority","high");document.head.appendChild(l);}catch(e){}})();`;
}
