/**
 * The ghost of a finding (Night Pharmacy; steering design.md "Ghost"): glowing mist, not a
 * sticker. A semi-transparent body whose radial gradient runs from an ivory centre to a clear
 * edge, a soft teal outer glow (CSS drop-shadows), a wispy tapered tail that fades out, a slow
 * inner shimmer, and dark, soft eyes. Used on the home scenes and on the findings. Motion is CSS
 * only (`.ghost-*` in theme/home-scenes.css): idle float, tail wave, shimmer and an occasional
 * blink; `--lean` (deg) lets a parent tilt it toward the pointer. Every motion stops under
 * `prefers-reduced-motion`. The shape is decorative: the meaning is carried by the text next to
 * it, so it is always `aria-hidden`.
 */
import { useId } from "react";

export function Ghost({
  size = 34,
  animated = false,
  className = "",
}: {
  size?: number;
  animated?: boolean;
  className?: string;
}) {
  const id = useId().replace(/:/g, "");
  return (
    <svg
      viewBox="0 0 64 84"
      width={size}
      height={(size * 84) / 64}
      className={`ghost ${animated ? "ghost-animated" : ""} ${className}`}
      aria-hidden
      focusable="false"
    >
      <defs>
        <radialGradient id={`gb${id}`} cx="50%" cy="34%" r="66%">
          <stop offset="0%" stopColor="var(--ghost-core)" stopOpacity="0.88" />
          <stop offset="42%" stopColor="var(--ghost-core)" stopOpacity="0.6" />
          <stop offset="76%" stopColor="var(--ghost-edge)" stopOpacity="0.24" />
          <stop offset="100%" stopColor="var(--ghost-edge)" stopOpacity="0" />
        </radialGradient>
        {/* The tail fades out toward its tips. */}
        <linearGradient id={`gf${id}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="white" />
          <stop offset="52%" stopColor="white" />
          <stop offset="100%" stopColor="black" />
        </linearGradient>
        <mask id={`gm${id}`}>
          <rect
            x="-10"
            y="-10"
            width="84"
            height="104"
            fill={`url(#gf${id})`}
          />
        </mask>
        <radialGradient id={`gs${id}`} cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="var(--ghost-core)" stopOpacity="0.9" />
          <stop offset="100%" stopColor="var(--ghost-core)" stopOpacity="0" />
        </radialGradient>
        <filter id={`ge${id}`} x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="0.7" />
        </filter>
      </defs>
      <g className="ghost-body">
        <g mask={`url(#gm${id})`}>
          {/* Head and body tapering into wisps; the tail group waves. */}
          <path
            d="M32 6C19 6 11 16 11 30c0 11 2 19 5 26 3 8 8 15 13 22-1-7 1-11 5-8 0-7 5-10 8-6 1-7 6-9 9-7-3-6 2-13 3-19 1-3 2-6 2-8C56 16 46 6 32 6Z"
            fill={`url(#gb${id})`}
          />
          <path
            className="ghost-tail"
            d="M16 56c3 9 7 16 12 24-4-9-3-15 1-14-2-6 0-10 4-9"
            fill="none"
            stroke="var(--ghost-core)"
            strokeOpacity="0.35"
            strokeWidth="3"
            strokeLinecap="round"
          />
        </g>
        <ellipse
          className="ghost-shimmer"
          cx="27"
          cy="22"
          rx="9"
          ry="6"
          fill={`url(#gs${id})`}
        />
        <g
          className="ghost-eyes"
          fill="var(--ghost-eye)"
          fillOpacity="0.82"
          filter={`url(#ge${id})`}
        >
          <ellipse cx="25" cy="30" rx="3.2" ry="4.2" />
          <ellipse cx="39" cy="30" rx="3.2" ry="4.2" />
        </g>
      </g>
    </svg>
  );
}
