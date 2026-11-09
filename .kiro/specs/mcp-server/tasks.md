# Implementation Plan: Janus MCP server

- [x] 1. API route `GET /open/cascade-package/pipc` (`janus/open/router.py`), added to the public OpenAPI document;
  tests for rows, licences and 503. _Requirements: 1.1; design §2.1, DP6_
- [x] 2. Package `apps/mcp`: `config.py` (environment, errors name the variable), `client.py` (one call, timeout, no
  retry, error codes), `safety.py` (fixed texts), `server.py` (seven tools, annotations, instructions, stdio and
  streamable HTTP, quiet loggers). _Requirements: 1, 2, 3, 4_
- [x] 3. Tests against a stub API: P1–P7, tool list, configuration; integration test against a real API
  (`JANUS_MCP_INTEGRATION_URL`). _Requirements: 6_
- [x] 4. NOTICE entry for the MCP Python SDK (`pipelines/sources.toml`, regenerated NOTICE). _Requirements: 4.4_
- [x] 5. Docs: `docs/mcp.md` with Kiro and Claude configuration; `.kiro/settings/mcp.json`. _Requirements: 5_
- [x] 6. Reviews: safety-auditor and pharmacologist passes on tool descriptions and safety texts; fixes applied;
  sheets saved in this folder. _Requirements: 2_
- [x] 7. Checkpoint: ruff, ruff format, pyright, pytest for `apps/mcp`, `apps/api` and `pipelines`; CI job; commit.
  _Requirements: all_
