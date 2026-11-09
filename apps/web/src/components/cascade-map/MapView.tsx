"use client";
/**
 * The constellation (cascade-map design §6, Req 2, 6, 7): an SVG of the precomputed layout. Pan and
 * zoom write one `transform` attribute and the `--inv` property from a requestAnimationFrame; no
 * React render runs per pointer move (DP4). Stars use a roving tabindex; arrow keys move to the
 * nearest star in that direction (`move`), Enter or Space opens it.
 */
import {
  memo,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
  type PointerEvent,
} from "react";

import {
  byLabel,
  edgeGeometry,
  move,
  starField,
  type CannotCheck,
  type Direction,
  type Graph,
  type GraphEdge,
} from "@/cascade-map/model";
import { useT } from "@/theme/words";

export type Selection =
  { kind: "edge"; row: number } | { kind: "node"; id: string };

const KEYS: Record<string, Direction> = {
  ArrowLeft: "left",
  ArrowRight: "right",
  ArrowUp: "up",
  ArrowDown: "down",
};
const SKY = starField(110, 400, 500);
const MAX_ZOOM = 6;

const reducedMotion = () =>
  typeof matchMedia === "function" &&
  matchMedia("(prefers-reduced-motion: reduce)").matches;

function Icon({ d }: { d: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={22}
      height={22}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.9}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      focusable="false"
    >
      <path d={d} />
    </svg>
  );
}

export const MapView = memo(function MapView({
  graph,
  names,
  locale,
  edges,
  visible,
  matched,
  cannot,
  selected,
  onOpen,
  eventText,
}: {
  graph: Graph;
  names: Map<string, string>;
  locale: string;
  edges: GraphEdge[];
  visible: Set<string>;
  matched: Map<number, number[]>;
  cannot: Map<number, CannotCheck>;
  selected: Selection | null;
  onOpen: (s: Selection, opener: Element | null) => void;
  /** The side effect of a row as published, in the interface language. */
  eventText: (row: number) => string;
}) {
  const t = useT();
  const { width: W, height: H } = graph.canvas;
  const nodes = useMemo(
    () => new Map(graph.nodes.map((n) => [n.id, n])),
    [graph],
  );
  const order = useMemo(
    () => byLabel(visible, names, locale),
    [visible, names, locale],
  );
  const [active, setActive] = useState<string | null>(null);
  const current = active && visible.has(active) ? active : (order[0] ?? null);

  const box = useRef<HTMLDivElement>(null);
  const svg = useRef<SVGSVGElement>(null);
  const layer = useRef<SVGGElement>(null);
  const els = useRef(new Map<string, SVGGElement>());
  const view = useRef({ k: 1, x: 0, y: 0 });
  const fit = useRef({ k: 1, x: 0, y: 0 });
  const size = useRef({ w: 0, h: 0 });
  const frame = useRef(0);

  const invK = useRef(0);
  const labelEls = useRef(new Map<string, SVGTextElement>());
  const textWidth = useRef(new Map<string, number>());
  const placeLabels = useRef(() => {});
  /**
   * Writes the transform. `--inv` restyles every star, label and arrowhead, so during a gesture it
   * follows the zoom in steps of 8 % (a few pixels on a star, not seen) and exactly when the
   * gesture ends (design §7).
   */
  const apply = useCallback((exact = false) => {
    frame.current = 0;
    const { k, x, y } = view.current;
    layer.current?.setAttribute(
      "transform",
      `translate(${x.toFixed(1)} ${y.toFixed(1)}) scale(${k.toFixed(4)})`,
    );
    if (exact === true || Math.abs(k / invK.current - 1) > 0.08) {
      invK.current = k;
      svg.current?.style.setProperty("--inv", (1 / k).toFixed(4));
      // Labels are placed once the zoom settles: placing them per step cost 50-66 ms at 4x CPU.
      if (exact === true) placeLabels.current();
    }
  }, []);
  const schedule = useCallback(() => {
    if (!frame.current) frame.current = requestAnimationFrame(() => apply());
  }, [apply]);

  /** Keeps the scale in range and at least half of the map in view. */
  const clamp = useCallback(() => {
    const v = view.current;
    const { w, h } = size.current;
    v.k = Math.min(
      fit.current.k * MAX_ZOOM,
      Math.max(fit.current.k * 0.9, v.k),
    );
    v.x = Math.min(w / 2, Math.max(w / 2 - W * v.k, v.x));
    v.y = Math.min(h / 2, Math.max(h / 2 - H * v.k, v.y));
  }, [W, H]);

  const tween = useRef(0);
  const animateTo = useCallback(
    (to: { k: number; x: number; y: number }) => {
      cancelAnimationFrame(tween.current);
      if (reducedMotion()) {
        view.current = { ...to };
        cancelAnimationFrame(frame.current);
        frame.current = requestAnimationFrame(() => apply(true));
        return;
      }
      const from = { ...view.current };
      const t0 = performance.now();
      const step = (now: number) => {
        const p = Math.min(1, (now - t0) / 180);
        const e = 1 - (1 - p) ** 3;
        view.current = {
          k: from.k + (to.k - from.k) * e,
          x: from.x + (to.x - from.x) * e,
          y: from.y + (to.y - from.y) * e,
        };
        apply(p === 1);
        if (p < 1) tween.current = requestAnimationFrame(step);
      };
      tween.current = requestAnimationFrame(step);
    },
    [apply],
  );

  const zoomAt = useCallback(
    (factor: number, cx: number, cy: number, animate: boolean) => {
      const v = view.current;
      const k = Math.min(
        fit.current.k * MAX_ZOOM,
        Math.max(fit.current.k * 0.9, v.k * factor),
      );
      const next = {
        k,
        x: cx - ((cx - v.x) * k) / v.k,
        y: cy - ((cy - v.y) * k) / v.k,
      };
      if (animate) {
        const saved = view.current;
        view.current = next;
        clamp();
        const target = view.current;
        view.current = saved;
        animateTo(target);
      } else {
        view.current = next;
        clamp();
        schedule();
      }
    },
    [animateTo, clamp, schedule],
  );

  const reset = useCallback(() => animateTo({ ...fit.current }), [animateTo]);

  // Fit to the box on mount and on resize (not per frame).
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const ro = new ResizeObserver(() => {
      const w = el.clientWidth;
      const h = el.clientHeight;
      if (!w || !h) return;
      const first = size.current.w === 0;
      const ratio = view.current.k / fit.current.k;
      size.current = { w, h };
      const k = Math.min(w / W, h / H);
      fit.current = { k, x: (w - W * k) / 2, y: (h - H * k) / 2 };
      view.current = first
        ? { ...fit.current }
        : { ...fit.current, k: k * ratio };
      clamp();
      apply(true);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [W, H, apply, clamp]);

  // Ctrl/⌘ + wheel (and trackpad pinch) zooms; a plain wheel scrolls the page.
  useEffect(() => {
    const el = svg.current;
    if (!el) return;
    let settle = 0;
    const onWheel = (e: WheelEvent) => {
      if (!e.ctrlKey && !e.metaKey) return;
      e.preventDefault();
      clearTimeout(settle);
      settle = window.setTimeout(() => apply(true), 150);
      const r = el.getBoundingClientRect();
      zoomAt(
        Math.exp(-Math.max(-60, Math.min(60, e.deltaY)) * 0.006),
        e.clientX - r.left,
        e.clientY - r.top,
        false,
      );
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => {
      clearTimeout(settle);
      el.removeEventListener("wheel", onWheel);
    };
  }, [zoomAt, apply]);

  useEffect(
    () => () => {
      cancelAnimationFrame(frame.current);
      cancelAnimationFrame(tween.current);
    },
    [],
  );

  // --- pointer: drag pans, two pointers pinch, a short tap opens the nearest star or a line ---
  const pointers = useRef(new Map<number, { x: number; y: number }>());
  const gesture = useRef<{
    rect: DOMRect;
    sx: number;
    sy: number;
    start: { k: number; x: number; y: number };
    moved: number;
    pinched: boolean;
    target: EventTarget | null;
    pinch: { d: number; k: number } | null;
  } | null>(null);

  const local = (e: PointerEvent, rect: DOMRect) => ({
    x: e.clientX - rect.left,
    y: e.clientY - rect.top,
  });

  const onPointerDown = (e: PointerEvent<SVGSVGElement>) => {
    if (e.pointerType === "mouse" && e.button !== 0) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    const rect =
      gesture.current?.rect ?? e.currentTarget.getBoundingClientRect();
    const p = local(e, rect);
    pointers.current.set(e.pointerId, p);
    cancelAnimationFrame(tween.current);
    if (pointers.current.size === 1) {
      gesture.current = {
        rect,
        sx: p.x,
        sy: p.y,
        start: { ...view.current },
        moved: 0,
        pinched: false,
        target: e.target,
        pinch: null,
      };
    } else if (pointers.current.size === 2 && gesture.current) {
      const [a, b] = [...pointers.current.values()];
      gesture.current.pinched = true;
      gesture.current.pinch = {
        d: Math.hypot(a!.x - b!.x, a!.y - b!.y),
        k: view.current.k,
      };
    }
  };

  const onPointerMove = (e: PointerEvent<SVGSVGElement>) => {
    const g = gesture.current;
    if (!g || !pointers.current.has(e.pointerId)) return;
    const p = local(e, g.rect);
    pointers.current.set(e.pointerId, p);
    if (g.pinch && pointers.current.size >= 2) {
      const [a, b] = [...pointers.current.values()];
      const d = Math.hypot(a!.x - b!.x, a!.y - b!.y);
      zoomAt(
        (g.pinch.k * d) / g.pinch.d / view.current.k,
        (a!.x + b!.x) / 2,
        (a!.y + b!.y) / 2,
        false,
      );
      return;
    }
    if (g.pinched) return;
    const dx = p.x - g.sx;
    const dy = p.y - g.sy;
    g.moved = Math.max(g.moved, Math.hypot(dx, dy));
    if (g.moved < 4) return;
    view.current = { ...view.current, x: g.start.x + dx, y: g.start.y + dy };
    clamp();
    schedule();
  };

  const onPointerUp = (e: PointerEvent<SVGSVGElement>) => {
    const g = gesture.current;
    pointers.current.delete(e.pointerId);
    if (pointers.current.size > 0 || !g) return;
    gesture.current = null;
    // The zoom (pinch) or the view (drag) changed: settle the labels once.
    if (g.pinched || g.moved >= 6) requestAnimationFrame(() => apply(true));
    if (g.pinched || g.moved >= 6 || e.type === "pointercancel") return;
    // A tap: the nearest visible star within 26 px wins over the line under the finger.
    const v = view.current;
    const px = (g.sx - v.x) / v.k;
    const py = (g.sy - v.y) / v.k;
    let best: { id: string; d: number } | null = null;
    for (const id of visible) {
      const n = nodes.get(id)!;
      const d = Math.hypot(n.x - px, n.y - py) * v.k;
      if (d <= 26 && (!best || d < best.d)) best = { id, d };
    }
    if (best) {
      setActive(best.id);
      onOpen({ kind: "node", id: best.id }, els.current.get(best.id) ?? null);
      return;
    }
    const row = (g.target as Element | null)
      ?.closest?.("[data-row]")
      ?.getAttribute("data-row");
    if (row) onOpen({ kind: "edge", row: Number(row) }, null);
  };

  // --- keyboard ---------------------------------------------------------------------------------
  const focusPending = useRef(false);
  useEffect(() => {
    if (!focusPending.current || !current) return;
    focusPending.current = false;
    els.current.get(current)?.focus({ preventScroll: true });
  }, [current]);

  /** Pans so that a star is inside the box (keyboard moves can leave the view). */
  const reveal = (id: string) => {
    const n = nodes.get(id);
    if (!n) return;
    const v = view.current;
    const { w, h } = size.current;
    const sx = n.x * v.k + v.x;
    const sy = n.y * v.k + v.y;
    const pad = 56;
    let x = v.x;
    let y = v.y;
    if (sx < pad) x += pad - sx;
    if (sx > w - pad) x -= sx - (w - pad);
    if (sy < pad) y += pad - sy;
    if (sy > h - pad) y -= sy - (h - pad);
    if (x !== v.x || y !== v.y) animateTo({ k: v.k, x, y });
  };

  const go = (id: string) => {
    focusPending.current = true;
    setActive(id);
    reveal(id);
    if (id === current) els.current.get(id)?.focus({ preventScroll: true });
  };

  const onNodeKey = (e: KeyboardEvent<SVGGElement>, id: string) => {
    const dir = KEYS[e.key];
    if (dir) {
      e.preventDefault();
      go(move(nodes, visible, id, dir));
    } else if (e.key === "Home" || e.key === "End") {
      e.preventDefault();
      const target = e.key === "Home" ? order[0] : order[order.length - 1];
      if (target) go(target);
    } else if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onOpen({ kind: "node", id }, e.currentTarget);
    } else if (e.key === "+" || e.key === "=" || e.key === "-") {
      e.preventDefault();
      const { w, h } = size.current;
      zoomAt(e.key === "-" ? 1 / 1.5 : 1.5, w / 2, h / 2, true);
    }
  };

  // --- drawing ------------------------------------------------------------------------------------
  const degree = useMemo(() => {
    const d = new Map<string, number>();
    for (const e of graph.edges) {
      d.set(e.from, (d.get(e.from) ?? 0) + 1);
      d.set(e.to, (d.get(e.to) ?? 0) + 1);
    }
    return d;
  }, [graph]);
  const starNames = useMemo(() => {
    const shown = new Set(edges.map((e) => e.row));
    return new Map(
      graph.nodes.map((n) => [
        n.id,
        t("CascadeMap.star", {
          name: names.get(n.id) ?? n.id,
          index: n.index.filter((r) => shown.has(r)).length,
          marker: n.marker.filter((r) => shown.has(r)).length,
        }),
      ]),
    );
  }, [graph, edges, names, t]);
  const mine = useMemo(
    () =>
      new Set(
        edges.filter((e) => matched.has(e.row)).flatMap((e) => [e.from, e.to]),
      ),
    [edges, matched],
  );
  const selEdge =
    selected?.kind === "edge"
      ? graph.edges.find((e) => e.row === selected.row)
      : undefined;
  const selNode = selected?.kind === "node" ? selected.id : null;
  const selMid = selEdge
    ? edgeGeometry(nodes.get(selEdge.from)!, nodes.get(selEdge.to)!)
    : null;
  const focusIds = new Set(
    selEdge
      ? [selEdge.from, selEdge.to]
      : selNode
        ? [
            selNode,
            ...edges
              .filter((e) => e.from === selNode || e.to === selNode)
              .flatMap((e) => [e.from, e.to]),
          ]
        : [],
  );
  /**
   * Which stars are named at this zoom (design §6): the focused and selected ones always, then the
   * person's matches, then by number of patterns; a label is shown only where it overlaps no star
   * and no label already placed. Runs when the zoom settles or steps, not per pan frame.
   */
  const labelOrder = useMemo(() => {
    const rank = (id: string) =>
      (focusIds.has(id) || current === id ? 2000 : 0) +
      (mine.has(id) ? 1000 : 0) +
      (degree.get(id) ?? 0);
    return [...visible].sort((a, b) => rank(b) - rank(a) || (a < b ? -1 : 1));
    // focusIds is derived from selection and edges; its identity changes every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visible, selected, edges, mine, degree, current]);
  const always = useMemo(
    () => new Set([...focusIds, ...(current ? [current] : [])]),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [labelOrder],
  );
  useEffect(() => {
    placeLabels.current = () => {
      const { k, x, y } = view.current;
      const { w: w0, h: h0 } = size.current;
      const boxes: [number, number, number, number][] = [];
      for (const id of visible) {
        const n = nodes.get(id)!;
        boxes.push([n.x * k - 7, n.y * k - 7, n.x * k + 7, n.y * k + 7]);
      }
      // Text widths do not depend on the zoom (labels are counter-scaled): read them once, all
      // before the first write, so placing never forces a layout per label.
      for (const id of labelOrder) {
        const el = labelEls.current.get(id);
        if (el && !textWidth.current.has(id))
          textWidth.current.set(id, el.getComputedTextLength());
      }
      labelOrder.forEach((id) => {
        const el = labelEls.current.get(id);
        const n = nodes.get(id);
        if (!el || !n) return;
        const w = textWidth.current.get(id) ?? 0;
        const off = (degree.get(id) ?? 0) >= 4 ? 12 : 10;
        const sx = n.x * k;
        const sy = n.y * k;
        type Box = [number, number, number, number];
        const at = (side: "l" | "r"): Box =>
          side === "l"
            ? [sx - off - w - 2, sy - 9, sx - off + 2, sy + 6]
            : [sx + off - 2, sy - 9, sx + off + w + 2, sy + 6];
        // Inside the visible box (labels are in layout × k space; the view adds x, y).
        const inside = (b: Box) =>
          b[0] + x >= 4 &&
          b[2] + x <= w0 - 4 &&
          b[1] + y >= 0 &&
          b[3] + y <= h0;
        const free = (b: Box) =>
          inside(b) &&
          !boxes.some(
            (o) => o[0] < b[2] && b[0] < o[2] && o[1] < b[3] && b[1] < o[3],
          );
        // The generator's side first, then the other one.
        const other = n.side === "l" ? "r" : "l";
        const side = free(at(n.side)) || always.has(id) ? n.side : other;
        const box = at(side);
        const show = always.has(id) || free(box);
        el.setAttribute("x", String(side === "l" ? -off : off));
        el.setAttribute("text-anchor", side === "l" ? "end" : "start");
        el.setAttribute("visibility", show ? "visible" : "hidden");
        if (show) boxes.push(box);
      });
    };
    placeLabels.current();
  }, [labelOrder, always, visible, nodes, degree]);
  // Widths measured before the web fonts arrived are measured again once they have.
  useEffect(() => {
    let live = true;
    void document.fonts?.ready.then(() => {
      if (!live) return;
      textWidth.current.clear();
      placeLabels.current();
    });
    return () => {
      live = false;
    };
  }, []);

  const drawn = useMemo(() => {
    const rank = (e: GraphEdge) =>
      matched.has(e.row) ? 2 : cannot.has(e.row) ? 1 : 0;
    return [...edges]
      .sort((a, b) => rank(a) - rank(b) || a.row - b.row)
      .map((e) => ({
        e,
        g: edgeGeometry(nodes.get(e.from)!, nodes.get(e.to)!),
      }));
  }, [edges, matched, cannot, nodes]);

  const edgeClass = (e: GraphEdge) =>
    [
      matched.has(e.row)
        ? "cm-e-matched"
        : cannot.has(e.row)
          ? "cm-e-cannot"
          : "",
      selEdge?.row === e.row ? "cm-e-selected" : "",
      (selEdge && selEdge.row !== e.row) ||
      (selNode && e.from !== selNode && e.to !== selNode)
        ? "cm-e-dim"
        : "",
    ].join(" ");

  const truncate = (s: string) =>
    s.length > 26 ? `${s.slice(0, 24).trimEnd()}…` : s;
  const zoomBy = (f: number) =>
    zoomAt(f, size.current.w / 2, size.current.h / 2, true);

  return (
    <div
      ref={box}
      className="cm-map aspect-[4/5] w-full lg:aspect-auto lg:h-[min(76svh,780px)]"
      data-testid="cascade-map"
    >
      <svg
        className="cm-sky absolute inset-0"
        viewBox="0 0 400 500"
        preserveAspectRatio="xMidYMid slice"
        aria-hidden
        focusable="false"
      >
        {SKY.map((s, i) => (
          <circle key={i} cx={s.x} cy={s.y} r={s.r / 2} opacity={s.o} />
        ))}
      </svg>
      <svg
        ref={svg}
        className="absolute inset-0"
        role="group"
        aria-label={t("CascadeMap.mapLabel", { total: graph.edges.length })}
        aria-describedby="cm-keys"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
      >
        <g ref={layer}>
          <g aria-hidden="true">
            {drawn.map(({ e, g }) => (
              <g
                key={e.row}
                data-row={e.row}
                className={edgeClass(e)}
                data-testid={`edge-${e.row}`}
              >
                <path
                  className="cm-edge"
                  d={g.d}
                  vectorEffect="non-scaling-stroke"
                />
                <path
                  className="cm-hit"
                  d={g.d}
                  vectorEffect="non-scaling-stroke"
                />
                <path
                  className="cm-arrow"
                  d="M0 0L-10 -5L-10 5Z"
                  style={{
                    transform: `translate(${nodes.get(e.to)!.x}px, ${nodes.get(e.to)!.y}px) rotate(${g.angle}deg) scale(var(--inv, 1)) translate(-9px, 0)`,
                  }}
                />
              </g>
            ))}
            {selEdge && edges.includes(selEdge) ? (
              <g
                style={{
                  transform: `translate(${selMid!.mid[0]}px, ${selMid!.mid[1]}px) scale(var(--inv, 1)) translate(${(selMid!.out[0] * 18).toFixed(1)}px, ${(selMid!.out[1] * 18).toFixed(1)}px)`,
                }}
              >
                <text
                  className="cm-label cm-label-event"
                  textAnchor="middle"
                  y={4}
                >
                  {truncate(eventText(selEdge.row))}
                </text>
              </g>
            ) : null}
          </g>
          {graph.nodes
            .filter((n) => visible.has(n.id))
            .map((n) => {
              const name = names.get(n.id) ?? n.id;
              const hub = (degree.get(n.id) ?? 0) >= 4;
              const dim = selected && !focusIds.has(n.id);
              const cls = [
                "cm-node",
                selNode === n.id ? "cm-n-selected" : "",
                dim ? "cm-n-dim" : "",
              ].join(" ");
              const label = starNames.get(n.id) ?? name;
              return (
                <g
                  key={n.id}
                  ref={(el) => {
                    if (el) els.current.set(n.id, el);
                    else els.current.delete(n.id);
                  }}
                  transform={`translate(${n.x} ${n.y})`}
                  className={cls}
                  role="button"
                  tabIndex={current === n.id ? 0 : -1}
                  aria-label={
                    mine.has(n.id)
                      ? `${label} ${t("CascadeMap.inYourFindings")}`
                      : label
                  }
                  data-node={n.id}
                  onKeyDown={(e) => onNodeKey(e, n.id)}
                  onFocus={() => setActive(n.id)}
                  onClick={(e) => {
                    // Assistive technologies send a click; pointer taps are handled in onPointerUp.
                    if (e.detail === 0)
                      onOpen({ kind: "node", id: n.id }, e.currentTarget);
                  }}
                >
                  <g className="cm-glyph">
                    <circle className="cm-hit-node" r={23} />
                    <circle className="cm-glow" r={hub ? 13 : 10} />
                    {mine.has(n.id) ? (
                      <circle className="cm-mine" r={hub ? 12 : 10} />
                    ) : null}
                    {current === n.id || selNode === n.id ? (
                      <circle className="cm-ring" r={hub ? 16 : 14} />
                    ) : null}
                    <circle className="cm-star" r={hub ? 6.5 : 4.5} />
                  </g>
                </g>
              );
            })}
          <g aria-hidden="true">
            {graph.nodes
              .filter((n) => visible.has(n.id))
              .map((n) => {
                const hub = (degree.get(n.id) ?? 0) >= 4;
                return (
                  <g
                    key={n.id}
                    transform={`translate(${n.x} ${n.y})`}
                    className={
                      selected && !focusIds.has(n.id) ? "cm-n-dim" : undefined
                    }
                  >
                    <text
                      ref={(el) => {
                        if (el) labelEls.current.set(n.id, el);
                        else labelEls.current.delete(n.id);
                      }}
                      visibility="hidden"
                      className="cm-label cm-glyph"
                      x={(hub ? 12 : 10) * (n.side === "l" ? -1 : 1)}
                      y={4.5}
                      textAnchor={n.side === "l" ? "end" : "start"}
                    >
                      {truncate(names.get(n.id) ?? n.id)}
                    </text>
                  </g>
                );
              })}
          </g>
        </g>
      </svg>
      <div className="cm-controls">
        <button
          type="button"
          onClick={() => zoomBy(1.5)}
          aria-label={t("CascadeMap.zoom.in")}
          title={t("CascadeMap.zoom.in")}
        >
          <Icon d="M12 5v14M5 12h14" />
        </button>
        <button
          type="button"
          onClick={() => zoomBy(1 / 1.5)}
          aria-label={t("CascadeMap.zoom.out")}
          title={t("CascadeMap.zoom.out")}
        >
          <Icon d="M5 12h14" />
        </button>
        <button
          type="button"
          onClick={reset}
          aria-label={t("CascadeMap.zoom.reset")}
          title={t("CascadeMap.zoom.reset")}
        >
          <Icon d="M8 3H5a2 2 0 0 0-2 2v3M21 8V5a2 2 0 0 0-2-2h-3M3 16v3a2 2 0 0 0 2 2h3M16 21h3a2 2 0 0 0 2-2v-3" />
        </button>
      </div>
    </div>
  );
});
