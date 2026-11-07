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

### Agent hooks

- Added hooks in `.kiro/hooks/`: `medical-language-guard`, `log-guard`, `license-guard`
  (+ `-create`) and `translation-completeness` run shell commands (no credits);
  `kiro-log` (PostTaskExec) and `kiro-log-stop` (Stop) are agent prompts that write this log.
- Each guard was tested against a planted violation: the medical-language guard flagged
  `"gereksiz ilaç"` and `"stop taking"` with path:line; log-guard flagged
  `logger.info(..., ingredients)` and an `atc_code` in `extra`; license-guard flagged a
  renamed CSV by its TİTCK column headers (BARKOD, ÜRÜN ADI, ETKİN MADDE, ATC KODU).
- Testing the translation hook showed the key-parity test did not say which key was
  missing; it now names missing and extra keys (`Home.status` in `de.json`).
- The phrase scan of `apps/` is a vitest test (`source-scan.test.ts`), so CI enforces it too:
  Node here is built without TypeScript stripping, so a standalone script couldn't reuse the
  phrase list.

- `kiro-log-stop` is disabled (`"enabled": false`): it fires an agent prompt at the end of
  every run, which costs credits even when it decides there is nothing to log. The
  `kiro-log` hook on spec-task completion stays on and is now the only automatic log writer.

### Custom agents

- Added five workspace agents in `.kiro/agents/` (Markdown with YAML front matter):
  `pharmacologist`, `statistician`, `historian` (can write, no web), `safety-auditor` and
  `localization-reviewer` (read-only: `read` tool only, no write or shell).
- Each agent loads the steering files for its area through `resources`.

### Open items

- **arm64 image build not verified.** Images currently build and run on amd64 only; base
  images and lockfiles support arm64, but no arm64 build has run (no QEMU emulation set up,
  by decision). The Oracle Cloud shape (Ampere arm64 or x86) is decided at the end of
  Phase 3; if arm64 is chosen, verify with `docker buildx build --platform linux/arm64`
  before Phase 5.
- **Hooks not yet seen firing in the IDE.** Hook files load at session start; the command
  hooks were run by hand with a sample event, and the `kiro-log` prompt was followed by hand.
  Confirm in the next session; watch `kiro-log-stop` for repeated no-op runs (credit cost).
