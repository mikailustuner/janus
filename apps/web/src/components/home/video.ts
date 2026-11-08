/**
 * The door transition video (DP49): WebM VP9 then H.264 MP4, 640 px on phones and 1280 px
 * elsewhere, the first frame as the poster while it loads. Idempotent: the idle preload and
 * "Step inside" both call it. When the last source fails the stage gets `data-still="video"`,
 * so the next "Step inside" goes straight to the room.
 */
export function loadDoorVideo(video: HTMLVideoElement): void {
  if (video.dataset.loaded) return;
  video.dataset.loaded = "1";
  const width = matchMedia("(max-width: 767px)").matches ? 640 : 1280;
  video.poster = "/home/door-poster.webp";
  let last: HTMLSourceElement | null = null;
  for (const [type, ext] of [
    ["video/webm", "webm"],
    ["video/mp4", "mp4"],
  ] as const) {
    last = document.createElement("source");
    last.type = type;
    last.src = `/home/door-${width}.${ext}`;
    video.appendChild(last);
  }
  last?.addEventListener("error", () =>
    video.closest(".np")?.setAttribute("data-still", "video"),
  );
  video.preload = "auto";
  video.load();
}
