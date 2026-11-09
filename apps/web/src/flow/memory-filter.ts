/**
 * The Collective Memory filter (experience Req 29.7, DP56): which of the separate panels are shown.
 * `all` (the default) shows every panel; the donated and outcome panels go together, and the
 * chosen event's safety line goes with them (Req 7). The layers are never combined, only hidden.
 */
export const MEMORY_FILTERS = ["all", "together", "regions", "janus"] as const;
export type MemoryFilter = (typeof MEMORY_FILTERS)[number];

export type MemoryPanels = {
  combination: boolean;
  regions: boolean;
  /** Donated reports and doctor-note outcomes, with the event picker and its safety line. */
  janus: boolean;
};

export function memoryPanels(filter: MemoryFilter): MemoryPanels {
  return {
    combination: filter === "all" || filter === "together",
    regions: filter === "all" || filter === "regions",
    janus: filter === "all" || filter === "janus",
  };
}
