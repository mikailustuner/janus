/**
 * The light-face calls (light-face design §9), through the experience HTTP client: same-origin
 * `/api`, timeouts, no retry, typed errors. Requests carry no user data; the goal key travels in a
 * POST body so that it never appears in a URL or an access log. Not part of demo mode (DP18).
 */
import { HttpClient, type Result } from "@/api/client";

import {
  cardsOut,
  exportOut,
  overviewOut,
  validationOut,
  type CardsOut,
  type ExportOut,
  type OverviewOut,
  type ValidationOut,
} from "./model";

export interface LightClient {
  overview(): Promise<Result<OverviewOut>>;
  cards(goal: string, offset: number, limit: number): Promise<Result<CardsOut>>;
  validation(): Promise<Result<ValidationOut>>;
  exportData(): Promise<Result<ExportOut>>;
}

const http = new HttpClient();

export const lightClient: LightClient = {
  overview: () => http.call("light/overview", "GET", null, overviewOut),
  cards: (goal, offset, limit) =>
    http.call("light/cards", "POST", { goal, offset, limit }, cardsOut),
  validation: () => http.call("light/validation", "GET", null, validationOut),
  exportData: () => http.call("light/export", "GET", null, exportOut, 30_000),
};
