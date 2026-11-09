# Requirements: Janus MCP server

## Introduction
Owner goal 2026-11-09: turn Janus from a showcase into software that clinicians, researchers and AI assistants can
use. This feature adds a **Model Context Protocol (MCP) server** so that an assistant (Claude, Kiro, any MCP client)
can call Janus: resolve a medicine box or name, check a medicine list for possible prescribing cascades against the
PIPC rule list, read the open cascade package rows, and read the time machine catalogue and onset data.

The server is a **thin client of the Janus HTTP API**: same request and response contracts, same safety wording,
no second engine. Every medical decision stays in the API's deterministic code (tech.md "deterministic medicine, LLM
language"); the assistant only explains what the API returned.

## Glossary
- **MCP client:** the assistant host (Claude Desktop, Claude Code, Kiro) that starts the server and calls its tools.
- **Tool:** an MCP tool exposed by the server; each tool calls one Janus API route.
- **Safety block:** the fixed `janus_safety` object every tool result carries (disclaimer, wording rules, emergency
  line).
- **API base URL:** the Janus API the server calls (`JANUS_API_URL`, default `http://127.0.0.1:8000`).

## Requirements

### Requirement 1: Tools are thin clients of the API
1. THE server SHALL expose the tools `janus_resolve_code` (POST `/resolve/scan`), `janus_resolve_ndc`
   (POST `/resolve/ndc`), `janus_search_medicines` (POST `/resolve/search`), `janus_check_cascades`
   (POST `/cascades/evaluate`), `janus_cascade_package_rows` (GET `/open/cascade-package/pipc`),
   `janus_time_machine_catalogue` (GET `/timemachine/catalogue`) and `janus_time_machine_cascade`
   (GET `/timemachine/cascade/{id}`).
2. EACH tool SHALL send the API request body unchanged in meaning (same field names and limits as the API models)
   and SHALL return the API's JSON response unchanged under `result`.
3. THE server SHALL NOT compute, filter or re-rank cascade findings, resolution candidates or counts.
4. WHEN the API answers with an error, THE tool SHALL fail with the API's error code (and failing field names, never
   their values); WHEN the API cannot be reached, THE tool SHALL fail with `janus_api_unreachable`.
5. EVERY API call SHALL have a timeout (`JANUS_API_TIMEOUT`, default 10 s) and SHALL NOT be retried (POST routes are
   not assumed idempotent from the client's side).

### Requirement 2: Safety wording travels with every result
1. EVERY tool result SHALL carry the safety block with the disclaimer "Janus provides information, not medical advice.
   Research prototype — not a medical device." (medical-safety rule 9).
2. THE safety block and the tool descriptions SHALL tell the assistant to describe a finding as a "possible
   prescribing cascade" (a pattern in the published PIPC list), never as a verdict; never to advise starting, changing
   or ending a medicine; to say that a finding may be worth discussing with a doctor or pharmacist; and not to add
   risk ratings, scores or assessment badges.
3. THE safety block of `janus_check_cascades` SHALL repeat that the extra API warning "Do not stop this medicine
   suddenly." must be passed on wherever the API returns it, and that an empty findings list is not reassurance (the
   API's own "no pattern" statement is to be quoted as given).
4. THE safety block SHALL carry the emergency line: if the person reports chest pain, breathing difficulty, signs of
   stroke or a severe allergic reaction, the assistant says "Call emergency services" first (112 in TR/EU, 911 in US).
5. THE time machine tools SHALL state that counts are reports, not people; that FAERS is spontaneous reporting (not
   incidence, not deduplicated); and that the time machine is in silico and exploratory.
6. No tool description, safety block or server instruction SHALL contain a forbidden phrase of medical-safety rule 2
   in any of the five languages.

### Requirement 3: Privacy
1. THE server SHALL NOT log tool inputs or API responses (codes, names, ingredient keys, months, ids).
2. THE server SHALL keep nothing between calls (no cache, no file, no history of lists).
3. THE server SHALL send a medicine list only to the configured API base URL and nowhere else, over https unless
   the API is on the same computer (loopback host).
4. Errors built by the server SHALL contain fixed codes and field names only, never an input value. (An argument
   the MCP SDK rejects before the tool runs is quoted back to the calling client in the SDK's error text; it is
   not logged and reaches no third party.)

### Requirement 4: Transports and configuration
1. THE server SHALL run over stdio by default (`janus-mcp`) for local assistants.
2. THE server SHALL offer streamable HTTP (`janus-mcp --transport streamable-http`), bound to a loopback address
   only (127.0.0.1, localhost or ::1) until MCP authorization exists.
3. THE API base URL and timeout SHALL be read from the environment; an invalid value SHALL stop the server with the
   variable's name.
4. THE dependency SHALL be the official MCP Python SDK, pinned to an exact version, with its licence recorded in
   NOTICE (via `pipelines/sources.toml`).

### Requirement 5: Documentation and examples
1. `docs/mcp.md` SHALL describe the tools, the safety block, the privacy rules, how to run the server, and a Kiro and
   a Claude configuration example.
2. THE repository SHALL contain `.kiro/settings/mcp.json`, an example Kiro configuration that starts the server.

### Requirement 6: Tests
1. Unit and Hypothesis property tests SHALL run against a stub API (no network).
2. AN integration test SHALL run the tools against a real Janus API WHEN `JANUS_MCP_INTEGRATION_URL` is set, and skip
   otherwise.
