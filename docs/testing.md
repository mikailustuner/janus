# Testing

How the test suites stay deterministic, where they run, and what blocks a commit.

## Suites

| Suite | Command | Notes |
| --- | --- | --- |
| API (`apps/api`) | `scripts/test-db.sh` | Starts a throwaway PostgreSQL 16, runs `uv run pytest`, removes the server |
| MCP server (`apps/mcp`) | `cd apps/mcp && uv run pytest` | |
| Pipelines (`pipelines`) | `cd pipelines && uv run pytest` | |
| Web unit (`apps/web`) | `pnpm test` | Vitest |
| Web rendered (`apps/web`) | `pnpm build && pnpm e2e` | Playwright against the production build; the API is stubbed |

`scripts/test-db.sh [command ...]` runs any command with `JANUS_TEST_DATABASE_URL` pointing at a
throwaway server: its own container name, data in memory, a port Docker picks on 127.0.0.1, and the same
logging settings as production. Without the variable the database tests are skipped locally; in CI an
unset variable is an error.

## Hypothesis profiles

| Profile | Where | Behaviour |
| --- | --- | --- |
| `dev` | local default | random seeds, 100 examples |
| `ci` | every push and pull request | `derandomize=True`: the same examples on every run, so a red build is reproducible |
| `nightly` | `.github/workflows/nightly.yml` | random seeds, 1000 examples (200 for database properties), reproduction blob printed |

Select one with `HYPOTHESIS_PROFILE=<name>`. When the nightly run finds a counterexample, the failing
input is pinned on the property with `@example(...)` in the fix, so it is checked on every run from then on.

## Flaky tests

The nightly workflow runs every suite five times in parallel. A test that fails in some runs and passes in
others is flaky. It is either fixed or, with a written reason, quarantined: marked
`@pytest.mark.skip(reason="quarantine: <issue>")` or `test.fixme(...)` and listed below. The target is an
empty list.

Quarantined tests: none.

## Test data

Behaviour tests use small synthetic fixtures built through the production types and decoders
(`apps/web/src/test/fixtures/`). The recorded API answers (`*.recorded.json`) are the site's demo data and
change whenever the data is rebuilt; each has exactly one contract test (it decodes with the production
decoder and holds the minimum the demo needs), and no other test reads their content.

## Pre-commit gate

`scripts/install-hooks.sh` points git at `.githooks/` (git worktrees share the setting). Before each
commit the hook runs, for the packages with staged changes only:

- Python packages: `ruff check`, `ruff format --check`, `pyright`
- `apps/web`: `prettier --check`, `eslint`, `tsc`
- shell scripts in `deploy/`, `scripts/` and `.githooks/`: `shellcheck`

It also refuses private or local-only paths (`.env`, `docs/internal/`, `.claude/`, `.data/`, `.shots/`).
Bypassing it with `--no-verify` is not allowed; CI runs the same checks on every push.
