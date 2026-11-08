/**
 * FAERS locator of a finding and its Janus event key (Req 7.5, 16.1, P6). The locator is
 * `faers:ingredient=<key>;event=<key>;region=<region>;scope=<scope>` or null; when null the
 * event key comes from the vocabulary (`pipc_positions` of the rule's row).
 */
import type { Finding } from "@/api/contracts";
import { eventKeyForRule, type Loaded } from "@/vocabulary";

export interface Locator {
  ingredient: string;
  event: string;
  region: string;
  scope: string;
}

const LOCATOR =
  /^faers:ingredient=((?:Q[1-9][0-9]{0,9}|J[1-9][0-9]{0,5}));event=([a-z0-9][a-z0-9_.-]{0,39});region=(ALL|TR|EU|US|OTHER|UNKNOWN);scope=(suspect|any)$/;

export function parseLocator(s: string | null | undefined): Locator | null {
  const m = s ? LOCATOR.exec(s) : null;
  return m
    ? { ingredient: m[1]!, event: m[2]!, region: m[3]!, scope: m[4]! }
    : null;
}

export function formatLocator(l: Locator): string {
  return `faers:ingredient=${l.ingredient};event=${l.event};region=${l.region};scope=${l.scope}`;
}

export function eventKeyOf(
  f: Pick<Finding, "faers_locator" | "rule_id">,
  v: Loaded,
): string | null {
  return parseLocator(f.faers_locator)?.event ?? eventKeyForRule(v, f.rule_id);
}
