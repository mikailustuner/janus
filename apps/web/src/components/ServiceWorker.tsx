"use client";
/** Registers the service worker in production builds (DP22); nothing else. */
import { useEffect } from "react";

export function ServiceWorker() {
  useEffect(() => {
    if (
      process.env.NODE_ENV !== "production" ||
      !("serviceWorker" in navigator)
    )
      return;
    navigator.serviceWorker
      .register(`/sw.js?v=${process.env.NEXT_PUBLIC_JANUS_BUILD ?? "dev"}`, {
        scope: "/",
      })
      .catch(() => {
        /* no offline demo on this browser */
      });
  }, []);
  return null;
}
