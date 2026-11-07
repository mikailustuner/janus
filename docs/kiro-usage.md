# Kiro usage log

A dated log of how Kiro was used to build Janus: what specs caught, what property tests
found, what hooks blocked. Three to five lines per day.

## 2026-11-07 — Phase 0: repository skeleton

- Kiro (Vibe session, Autopilot) read the six steering files and the private planning
  documents, then proposed a plan for the Phase 0 skeleton. I approved it with changes
  (planning documents kept private in a gitignored folder) before any file was created.
- Kiro created the monorepo from `.kiro/steering/structure.md`: Next.js 16 web app
  (TypeScript strict, Tailwind v4, next-intl with EN/TR/DE/FR/ES, standalone output) and
  a FastAPI app (Python 3.12, uv, pytest, Hypothesis, ruff, pyright strict). The API has
  only empty modules and `/health`.
- Following `medical-safety.md`, Kiro added a test that checks every translation file for
  the forbidden phrases in all five languages, plus a key-parity check across languages.
- While wiring Docker Compose, Kiro found another local service already on port 3000 and
  moved the web port to 3100 (configurable) instead of stopping that service.
- CI (GitHub Actions) runs lint, type checks and tests, and fails if `.kiro/` is
  gitignored, a TİTCK list file is tracked, or a private planning document is tracked.
