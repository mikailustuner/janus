/**
 * The doctor page's logic (experience design §11, DP19, Req 19, P26, P27). Pure apart from the
 * injected fetch. The token is read from the URL fragment, kept only in this closure, and sent
 * only as `{token}` in the JSON bodies of `/api/outcomes/form` and `/api/outcomes`. A `demo-`
 * fragment and a fragment that is not a token send nothing.
 */
import { outcomesBody, PATTERNS, tokenOnlyBody } from "@/api/builders";
import { HttpClient, type Result } from "@/api/client";
import type {
  AnswerIn,
  OutcomeFormOut,
  OutcomeStoredOut,
} from "@/api/contracts";

export type Fragment =
  { kind: "demo"; patient: string } | { kind: "invalid" } | { kind: "token" };

export function readFragment(hash: string): Fragment {
  const f = hash.startsWith("#") ? hash.slice(1) : hash;
  const demo = /^demo-(istanbul|cologne|ohio)$/.exec(f);
  if (demo) return { kind: "demo", patient: demo[1]! };
  return PATTERNS.token.test(f) ? { kind: "token" } : { kind: "invalid" };
}

export type Fetch = (input: string, init: RequestInit) => Promise<Response>;

/** Holds the token for the life of the page; never stores or logs it. */
export function doctorSession(hash: string, fetchImpl: Fetch) {
  const f = hash.startsWith("#") ? hash.slice(1) : hash;
  const fragment = readFragment(f);
  const client = new HttpClient(fetchImpl);
  return {
    fragment,
    form(): Promise<Result<OutcomeFormOut>> | null {
      return fragment.kind === "token"
        ? client.outcomeForm(tokenOnlyBody(f))
        : null;
    },
    send(answers: AnswerIn[]): Promise<Result<OutcomeStoredOut>> | null {
      return fragment.kind === "token" && answers.length > 0
        ? client.outcomes(outcomesBody(f, answers))
        : null;
    },
  };
}

export type Assessment = "confirmed" | "not_a_cascade";
export type Action =
  "dose_changed" | "medicine_changed" | "stopped" | "no_change";
export interface Answer {
  assessment?: Assessment;
  action?: Action;
  actionOn?: "index" | "marker";
}

export const NEEDS_MEDICINE: ReadonlySet<string> = new Set([
  "dose_changed",
  "medicine_changed",
  "stopped",
]);

/** Answers for the API: unanswered findings left out, `action_on` exactly when required. */
export function buildAnswers(
  form: Pick<OutcomeFormOut, "findings">,
  state: Record<number, Answer>,
): AnswerIn[] | null {
  const out: AnswerIn[] = [];
  for (const f of form.findings) {
    const a = state[f.ref];
    if (!a?.assessment) continue;
    const answer: AnswerIn = { ref: f.ref, assessment: a.assessment };
    if (a.action) {
      if (NEEDS_MEDICINE.has(a.action)) {
        if (!a.actionOn) return null; // incomplete: the medicine the action concerns is missing
        answer.action_on = a.actionOn;
      }
      answer.action = a.action;
    }
    out.push(answer);
  }
  return out;
}

export function canSend(
  form: Pick<OutcomeFormOut, "findings">,
  state: Record<number, Answer>,
): boolean {
  const a = buildAnswers(form, state);
  return a !== null && a.length > 0;
}
