# Home scenes (experience DP46)

AI-generated with Google Gemini, **generated for Janus** (2026-11-08; the Clinical White hero by the owner, 2026-11-09); no third-party artwork, no real product or brand.
Listed in `NOTICE` (`pipelines/sources.toml`, id `art_home_scenes`).

| Files                                                          | Source                                                                                                     | Use                                                                                                                |
| -------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| `night-diorama-{2752,1600,960}.{avif,webp}`, `-{1600,960}.jpg` | `diorama-clean.jpg` (2752×1536)                                                                            | Night Pharmacy scene 1: isometric pharmacy at night, door ajar (ghosts are drawn in code)                          |
| `night-cabinet-…`                                              | `cabinet-iso.jpg` (2752×1536)                                                                              | Night Pharmacy scene 3: isometric cut-away room of the same house, open glowing cabinet, blank note on a table     |
| `clinical-hero-…`                                              | `Gemini_Generated_Image_xgsyxtxgsyxtxgsy.jpeg` (2752×1536; made by the owner in Google Gemini, 2026-11-09) | Glass Janus (Clinical White) hero: clear glass two-faced head filled with capsules on a white studio ground (DP68) |
| `door-{1280,640}.{mp4,webm}`, `door-poster.webp`               | `door-transition-iso.mp4` (1280×720, 24 fps, 10 s; the door opens, walls and roof dissolve into fireflies) | Night Pharmacy scene 2, played once after "Step inside" (DP49); the poster shows while it loads                    |

The sources are kept outside the repository. Conversion (ffmpeg 7 with libaom-av1, libwebp, libx264, libvpx-vp9):

```sh
# images, for each source and width W in 2752 1600 960 (JPEG at 1600 and 960 only)
ffmpeg -i SRC.jpg -vf scale=W:-2:flags=lanczos -c:v libaom-av1 -still-picture 1 -crf 30 -b:v 0 -cpu-used 4 -pix_fmt yuv420p NAME-W.avif
ffmpeg -i SRC.jpg -vf scale=W:-2:flags=lanczos -c:v libwebp -quality 80 NAME-W.webp
ffmpeg -i SRC.jpg -vf scale=W:-2:flags=lanczos -q:v 4 NAME-W.jpg
# video: no audio; a key frame every 6 frames (made for scrubbing, DP46; normal playback since DP49)
ffmpeg -i door-transition-iso.mp4 -an -c:v libx264 -preset slow -crf 23 -g 6 -keyint_min 6 -bf 0 -sc_threshold 0 -pix_fmt yuv420p -movflags +faststart -vf scale=1280:-2 door-1280.mp4
ffmpeg -i door-transition-iso.mp4 -an -c:v libvpx-vp9 -b:v 0 -crf 36 -g 6 -auto-alt-ref 0 -lag-in-frames 0 -row-mt 1 -vf scale=1280:-2 door-1280.webm
# 640 versions: the same with scale=640:-2 and crf 25 (mp4) / 38 (webm)
ffmpeg -i door-transition-iso.mp4 -vframes 1 -vf scale=1280:-2 -c:v libwebp -quality 78 door-poster.webp
```
