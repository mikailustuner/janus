# Janus MCP server

Janus provides information, not medical advice. Research prototype — not a medical device.

`apps/mcp` is a [Model Context Protocol](https://modelcontextprotocol.io) server that lets an AI assistant (Claude,
Kiro or any MCP client) use Janus: resolve a medicine box or name, check a medicine list for possible prescribing
cascades from the published PIPC list, read the PIPC rows of the open cascade package and the time machine data.

It is a **thin client of the Janus HTTP API**: every tool sends one request to the API and returns the API's JSON
unchanged. There is no second engine; whether a pattern exists is decided by the API's deterministic code. Spec:
[`.kiro/specs/mcp-server/`](../.kiro/specs/mcp-server/).

## Tools

| Tool | Janus API route | What it returns |
|---|---|---|
| `janus_resolve_code` | `POST /resolve/scan` | products and ingredients for a barcode (EAN-13 / GTIN) or a GS1 DataMatrix element string; `region` TR, US or EU |
| `janus_resolve_ndc` | `POST /resolve/ndc` | openFDA products for a US National Drug Code |
| `janus_search_medicines` | `POST /resolve/search` | products and ingredients by name (`region`, `limit` 1–20) |
| `janus_check_cascades` | `POST /cascades/evaluate` | possible prescribing cascades for 1–50 items (`product` candidate id or `ingredient` key, optional `choices`, optional `started` YYYY-MM) and the `dataset_version` of the resolve results |
| `janus_cascade_package_rows` | `GET /open/cascade-package/pipc` | the 65 PIPC rows (CC BY 4.0) with Janus's class mapping (Apache-2.0); `row` selects one |
| `janus_time_machine_catalogue` | `GET /timemachine/catalogue` | remedy and cascade ids, validation, sources |
| `janus_time_machine_cascade` | `GET /timemachine/cascade/{id}` | FAERS time to onset (reports, not people), published timing, populations |
| `janus_modelkit_search` | `GET /modelkit/drugs` | experimental drug model kit: drugs with a validation status (the first 50 matches); optional `query` keeps names containing it |
| `janus_modelkit_get` | `GET /modelkit/drugs/{key}` | one drug of the model kit: parameter set with evidence ids, validation report, what was left out. Research use only |

Every result is `{"janus_safety": {...}, "result": <the API's JSON>}`. Errors are fixed codes:
`janus_api_error: <code>` (with field names when the API names them), `janus_api_unreachable`,
`janus_api_bad_response`. Arguments outside the API's limits are refused before any request.

A typical conversation: resolve each medicine, confirm the candidate with the person, then call
`janus_check_cascades` with the `dataset_version` from the resolve result.

## Safety rules the server sends

The same rules are in the server instructions, in every tool description and in every result's `janus_safety`
block, because clients differ in what they show the model:

- The disclaimer: "Janus provides information, not medical advice. Research prototype — not a medical device."
- A finding is a **possible prescribing cascade**, a pattern in the published PIPC list, never a verdict.
- Never advise starting, changing or ending a medicine; a finding may be worth discussing with a doctor or
  pharmacist. No risk ratings, scores or assessment badges.
- `probable` means only that the start months fit the published time window; `possible` that timing is unknown or
  outside it; neither is a clinical judgement. `form_confirmed: false` means the dose form was not confirmed.
- Pass on "Do not stop this medicine suddenly." wherever the API returns it (word for word or as a faithful
  translation). An empty findings list is not reassurance: quote the API's statement as given. The rules apply in
  every language the assistant answers in.
- Emergency symptoms (chest pain, breathing difficulty, signs of stroke, severe allergic reaction): "Call emergency
  services" first (112 in Türkiye and the EU, 911 in the US).
- Time machine counts are reports, never people; FAERS is spontaneous reporting; the time machine is in silico and
  exploratory.

## Privacy

- The server logs nothing of a call: the SDK and HTTP-client loggers run at `WARNING`, and tool errors are fixed
  codes. (An argument the SDK rejects is quoted back to the calling client in its error message; it is not logged.)
- It keeps nothing between calls and talks only to `JANUS_API_URL`. The API itself is stateless for these routes and
  logs only an access line (route, status, latency).
- The medicines an assistant sends are seen by the assistant's provider as part of the conversation. Point
  `JANUS_API_URL` at an API you trust (by default the local one).

## Run it

Requirements: Python 3.12 and [uv](https://docs.astral.sh/uv/), and a Janus API with a loaded dataset (see the
README; locally `docker compose up`, or `uv run uvicorn janus.main:app` in `apps/api`).

```sh
cd apps/mcp
uv sync
JANUS_API_URL=http://127.0.0.1:8000 uv run janus-mcp                      # stdio (default)
JANUS_API_URL=http://127.0.0.1:8000 uv run janus-mcp --transport streamable-http --port 8765
#   → http://127.0.0.1:8765/mcp (no authentication: --host accepts only 127.0.0.1, localhost or ::1)
```

| Variable | Default | Meaning |
|---|---|---|
| `JANUS_API_URL` | `http://127.0.0.1:8000` | Janus API base URL: `https://host[:port][/path]`, or `http://` only for 127.0.0.1 / localhost (medicine lists never cross a network unencrypted); a deployment's API is at `/api` |
| `JANUS_API_TIMEOUT` | `10` | seconds per request, in (0, 60]; no retries |

## Kiro

The repository ships [`.kiro/settings/mcp.json`](../.kiro/settings/mcp.json), so Kiro starts the server for this
workspace:

```json
{
  "mcpServers": {
    "janus": {
      "command": "uv",
      "args": ["run", "--directory", "apps/mcp", "janus-mcp"],
      "env": { "JANUS_API_URL": "http://127.0.0.1:8000" },
      "disabled": false,
      "autoApprove": ["janus_cascade_package_rows", "janus_time_machine_catalogue", "janus_time_machine_cascade"]
    }
  }
}
```

Ask, for example: *"Use Janus to check amlodipine and furosemide for possible prescribing cascades."*

## Claude

Claude Code (from the repository root):

```sh
claude mcp add janus -e JANUS_API_URL=http://127.0.0.1:8000 -- uv run --directory apps/mcp janus-mcp
```

Claude Desktop (`claude_desktop_config.json`; use the absolute path of your checkout):

```json
{
  "mcpServers": {
    "janus": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/janus/apps/mcp", "janus-mcp"],
      "env": { "JANUS_API_URL": "http://127.0.0.1:8000" }
    }
  }
}
```

Any client that speaks streamable HTTP can use `http://127.0.0.1:8765/mcp` instead.

## Tests

```sh
cd apps/mcp
uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run pytest
JANUS_MCP_INTEGRATION_URL=http://127.0.0.1:8000 uv run pytest tests/test_integration.py   # against a real API
```

The unit and property tests use a stub API (no network). The integration test runs only when
`JANUS_MCP_INTEGRATION_URL` is set.

## Licence

The server is Apache-2.0 like the rest of Janus. It uses the official MCP Python SDK (`mcp`, MIT, pinned in
`apps/mcp/pyproject.toml`; listed in [NOTICE](../NOTICE)).
