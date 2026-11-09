#!/usr/bin/env bash
# Smoke test (deploy Req 8.1, C4, C5): key pages in two languages, the public API routes and the
# security headers. Usage: smoke.sh internal [tag]   (from inside the edge network)
#                          smoke.sh https://janusmeds.org [tag]
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
target="${1:?usage: smoke.sh internal|<https url> [tag]}"
tag="${2:-}"
if [ "$target" = internal ]; then
  base="http://web:3000"
  get() { docker run --rm --network janus-public-edge --read-only --cap-drop ALL curlimages/curl:8.17.0 "$@"; }
else
  base="$target"
  get() { curl "$@"; }
fi
fail=0
check() {  # check <path> <expected status>
  local code; code="$(get -s -o /dev/null -w '%{http_code}' -m 20 "$base$1" || true)"
  if [ "$code" = "$2" ]; then printf '  ok   %s %s\n' "$code" "$1"
  else printf '  FAIL %s %s (want %s)\n' "$code" "$1" "$2"; fail=1; fi
}
for lang in en tr; do
  for page in "" /demo /results /passport /research /research/time-machine /open-data /privacy; do
    check "/$lang$page" 200
  done
done
for route in /health /privacy/storage /memory/snapshot /seance/catalogue /light/overview \
  /timemachine/catalogue /open/outcomes; do
  check "/api$route" 200
done
# Static files outside the build output (public/): home media, fonts, service worker, scanner.
for asset in /home/door-1280.mp4 /home/door-poster.webp /home/night-cabinet-1600.avif \
  /home/glass-hero-1600.avif /fonts/Fraunces-SemiBold.ttf /sw.js /manifest.webmanifest \
  /vendor/zxing/zxing_reader.wasm /vendor/tesseract/worker.min.js /vendor/tesseract/lang/tur.traineddata; do
  check "$asset" 200
done
headers="$(get -sI -m 20 "$base/en")"
for h in content-security-policy referrer-policy x-content-type-options; do
  if grep -qi "^$h:" <<<"$headers"; then echo "  ok   header $h"; else echo "  FAIL header $h"; fail=1; fi
done
if grep -qi '^x-powered-by:' <<<"$headers"; then echo "  FAIL x-powered-by present"; fail=1; fi
if [ -n "$tag" ]; then
  health="$(get -s -m 20 "$base/api/health")"
  if grep -q "\"commit\":\"$tag\"" <<<"$health"; then echo "  ok   commit $tag"
  else echo "  FAIL /api/health commit is not $tag"; fail=1; fi
fi
if [ "$fail" = 0 ]; then log "smoke: ok ($target)"; else die "smoke: FAILED ($target)"; fi
