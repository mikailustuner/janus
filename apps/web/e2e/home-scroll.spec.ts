// Smooth scrolling of the home (experience Req 27.9, DP49): with the page loaded and idle, wheel
// through the whole home and back while recording long tasks (PerformanceObserver `longtask`)
// and frame intervals (requestAnimationFrame) between `performance.mark`s. No long task over
// 50 ms may happen during the scroll. Desktop runs at 1440 × 900, the phone project at 375 × 812;
// both themes. The numbers are printed and attached as annotations (recorded in design §16).
import { expect, test } from "@playwright/test";

import { THEMES, useTheme } from "./helpers";

type Stats = {
  longTasks: number[];
  frames: number;
  p95: number;
  worst: number;
  over50: number;
  distance: number;
};

for (const theme of THEMES)
  test(`scrolling the home has no long task, ${theme}`, async ({
    page,
  }, info) => {
    if (info.project.name === "desktop")
      await page.setViewportSize({ width: 1440, height: 900 });
    await useTheme(page, theme);
    await page.goto("/en", { waitUntil: "networkidle" });
    // Let hydration, the motion chunk and the idle video preload settle first.
    await page.waitForTimeout(2500);
    await page.evaluate(() => {
      const w = window as unknown as {
        __scroll: { longTasks: number[]; frames: number[]; on: boolean };
      };
      w.__scroll = { longTasks: [], frames: [], on: false };
      new PerformanceObserver((list) => {
        for (const e of list.getEntries())
          if (w.__scroll.on) w.__scroll.longTasks.push(e.duration);
      }).observe({ type: "longtask" });
      let last = 0;
      const tick = (t: number) => {
        if (w.__scroll.on && last) w.__scroll.frames.push(t - last);
        last = t;
        requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
      performance.mark("janus:scroll-start");
      w.__scroll.on = true;
    });
    const height = await page.evaluate(
      () => document.documentElement.scrollHeight - innerHeight,
    );
    const step = 120;
    for (let y = 0; y < height; y += step) {
      await page.mouse.wheel(0, step);
      await page.waitForTimeout(16);
    }
    for (let y = height; y > 0; y -= step) {
      await page.mouse.wheel(0, -step);
      await page.waitForTimeout(16);
    }
    await page.waitForTimeout(300);
    const stats: Stats = await page.evaluate((distance) => {
      const w = window as unknown as {
        __scroll: { longTasks: number[]; frames: number[]; on: boolean };
      };
      w.__scroll.on = false;
      performance.mark("janus:scroll-end");
      const f = [...w.__scroll.frames].sort((a, b) => a - b);
      return {
        longTasks: w.__scroll.longTasks,
        frames: f.length,
        p95: f[Math.floor(f.length * 0.95)] ?? 0,
        worst: f[f.length - 1] ?? 0,
        over50: f.filter((x) => x > 50).length,
        distance,
      };
    }, height * 2);
    const line = `[${info.project.name} ${theme}] scrolled ${stats.distance} px: ${stats.longTasks.length} long tasks${stats.longTasks.length ? ` (max ${Math.round(Math.max(...stats.longTasks))} ms)` : ""}; ${stats.frames} frames, p95 ${stats.p95.toFixed(1)} ms, worst ${stats.worst.toFixed(1)} ms, ${stats.over50} over 50 ms`;
    console.log(line);
    info.annotations.push({ type: "scroll", description: line });
    expect(stats.distance).toBeGreaterThan(1000);
    expect(stats.longTasks).toEqual([]);
  });
