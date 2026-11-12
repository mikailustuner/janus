"""The Janus MCP server (mcp-server design §2-§6).

Nine read-only tools, each one call to the Janus API. Arguments are checked with the API's own
limits before a request is sent; results are the API's JSON under `result`, next to the fixed
`janus_safety` block. Nothing is logged, cached or stored.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence
from typing import Annotated, Any, Final, Literal, cast
from urllib.parse import quote

import httpx2
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from janus_mcp import client, safety
from janus_mcp.config import LOOPBACK, Config, ConfigError, from_env

Region = Literal["TR", "US", "EU"]
QID = r"^(Q[1-9][0-9]{0,9}|J[1-9][0-9]{0,5})$"
CANDIDATE = r"^(TR|US|EU):[a-z_]+:[0-9]{1,9}$"
MONTH = r"^\d{4}-(0[1-9]|1[0-2])$"
CASCADE_ID = r"^[A-Za-z0-9_]{1,64}$"
DRUG_KEY = r"^[a-z][a-z0-9_]{0,31}$"
PARAMETER = r"^[a-z][a-z_]{0,15}$"
MAX_ITEMS: Final = 50
READ_ONLY: Final = ToolAnnotations(
    read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False
)


class Choice(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    position: Annotated[int, Field(ge=0, le=MAX_ITEMS - 1)]
    ingredient: Annotated[str, Field(pattern=QID)]


class Item(BaseModel):
    """One medicine: a product candidate id or an ingredient key, from a resolve result."""

    model_config = ConfigDict(extra="forbid", strict=True)
    product: Annotated[str, Field(pattern=CANDIDATE)] | None = None
    ingredient: Annotated[str, Field(pattern=QID)] | None = None
    choices: Annotated[list[Choice], Field(min_length=1, max_length=10)] | None = None
    started: Annotated[str, Field(pattern=MONTH)] | None = None


def _quiet_loggers() -> None:
    """No tool input or request URL in any log (privacy.md; design §5)."""
    for name in ("mcp", "httpx2", "httpcore", "uvicorn.access"):
        logging.getLogger(name).setLevel(logging.WARNING)


def build_server(config: Config, transport: httpx2.AsyncBaseTransport | None = None) -> MCPServer:
    server = MCPServer(
        name="janus",
        title="Janus prescribing-cascade check (research prototype)",
        instructions=safety.INSTRUCTIONS,
        version="0.1.0",
        log_level="WARNING",
    )
    _quiet_loggers()

    async def api(method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        try:
            return await client.call(config, method, path, body, transport)
        except client.ApiError as exc:
            raise ToolError(str(exc)) from None
        except Exception:
            raise ToolError("janus_mcp_internal_error") from None

    def result(payload: Any, *extra: str) -> dict[str, Any]:
        return {"janus_safety": safety.block(*extra), "result": payload}

    @server.tool(
        annotations=READ_ONLY,
        description=(
            "Resolve a medicine box code to products and ingredients (Janus POST /resolve/scan). "
            "`code` is the barcode digits (EAN-13, GTIN) or the GS1 DataMatrix element string; "
            "`region` (TR, US or EU) limits the search. Returns candidates with provenance and "
            "the dataset_version needed by janus_check_cascades. " + safety.DISCLAIMER
        ),
    )
    async def janus_resolve_code(
        code: Annotated[str, StringConstraints(min_length=1, max_length=512)],
        region: Region | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"content": code}
        if region is not None:
            body["region"] = region
        return result(await api("POST", "/resolve/scan", body), *safety.RESOLVE_LINES)

    @server.tool(
        annotations=READ_ONLY,
        description=(
            "Resolve a US National Drug Code (NDC, as printed on a pharmacy label) to openFDA "
            "products (Janus POST /resolve/ndc). " + safety.DISCLAIMER
        ),
    )
    async def janus_resolve_ndc(
        ndc: Annotated[str, StringConstraints(min_length=1, max_length=32)],
    ) -> dict[str, Any]:
        return result(await api("POST", "/resolve/ndc", {"ndc": ndc}), *safety.RESOLVE_LINES)

    @server.tool(
        annotations=READ_ONLY,
        description=(
            "Search medicines and ingredients by name in Türkiye, the EU and the US (Janus POST "
            "/resolve/search). `region` limits the search; `limit` is 1-20. " + safety.DISCLAIMER
        ),
    )
    async def janus_search_medicines(
        query: Annotated[
            str, StringConstraints(strip_whitespace=True, min_length=2, max_length=100)
        ],
        region: Region | None = None,
        limit: Annotated[int, Field(ge=1, le=20)] = 10,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"query": query, "limit": limit}
        if region is not None:
            body["region"] = region
        return result(await api("POST", "/resolve/search", body), *safety.RESOLVE_LINES)

    @server.tool(
        annotations=READ_ONLY,
        description=(
            "Check a medicine list for possible prescribing cascades from the published PIPC list "
            "(Janus POST /cascades/evaluate). Pass the dataset_version from the resolve results "
            "and 1-50 items, each with `product` (a candidate id) or `ingredient` (an ingredient "
            "key), optional `choices` for ambiguous ingredients and optional `started` (YYYY-MM). "
            "Each finding is a possible prescribing cascade with its PIPC row and evidence ids, "
            "never a verdict; never advise starting, changing or ending a medicine. "
            + safety.DISCLAIMER
        ),
    )
    async def janus_check_cascades(
        dataset_version: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")],
        items: Annotated[list[Item], Field(min_length=1, max_length=MAX_ITEMS)],
    ) -> dict[str, Any]:
        for it in items:
            if (it.product is None) == (it.ingredient is None):
                raise ToolError(
                    "invalid_arguments: each item needs exactly one of product and ingredient"
                )
            if it.choices is not None and it.product is None:
                raise ToolError("invalid_arguments: choices need a product")
        body = {
            "dataset_version": dataset_version,
            "items": [it.model_dump(exclude_none=True) for it in items],
        }
        payload = await api("POST", "/cascades/evaluate", body)
        return result(payload, *safety.CHECK_LINES)

    @server.tool(
        annotations=READ_ONLY,
        description=(
            "The 65 rows of the PIPC prescribing-cascade list (CC BY 4.0) with Janus's drug-class "
            "mapping, package version and citation (Janus GET /open/cascade-package/pipc). "
            "`row` (1-65) returns only that published row. " + safety.DISCLAIMER
        ),
    )
    async def janus_cascade_package_rows(
        row: Annotated[int, Field(ge=1, le=65)] | None = None,
    ) -> dict[str, Any]:
        payload = await api("GET", "/open/cascade-package/pipc")
        if row is not None and isinstance(payload, dict):
            obj = cast(dict[str, Any], payload)
            raw = obj.get("rows")
            rows = cast(list[Any], raw) if isinstance(raw, list) else []
            dicts = [cast(dict[str, Any], r) for r in rows if isinstance(r, dict)]
            kept: list[dict[str, Any]] = [r for r in dicts if r.get("position") == row]
            payload = {**obj, "rows": kept}
        return result(payload, *safety.PACKAGE_LINES)

    @server.tool(
        annotations=READ_ONLY,
        description=(
            "The time machine catalogue: remedy and cascade ids, validation block and sources "
            "(Janus GET /timemachine/catalogue). In silico and exploratory. " + safety.DISCLAIMER
        ),
    )
    async def janus_time_machine_catalogue() -> dict[str, Any]:
        payload = await api("GET", "/timemachine/catalogue")
        return result(payload, *safety.TIME_MACHINE_LINES)

    @server.tool(
        annotations=READ_ONLY,
        description=(
            "One cascade of the time machine: FAERS time to onset (reports, not people), the "
            "published timing and populations (Janus GET /timemachine/cascade/{cascade_id}); "
            "ids come from janus_time_machine_catalogue. " + safety.DISCLAIMER
        ),
    )
    async def janus_time_machine_cascade(
        cascade_id: Annotated[str, Field(pattern=CASCADE_ID)],
    ) -> dict[str, Any]:
        payload = await api("GET", f"/timemachine/cascade/{cascade_id}")
        return result(payload, *safety.TIME_MACHINE_LINES)

    @server.tool(
        annotations=READ_ONLY,
        description=(
            "Search the experimental drug model kit (Janus GET /modelkit/drugs): drugs with a "
            "parameter set built from cited evidence and a validation status. `query` keeps the "
            "drugs whose name contains it. Research use only. " + safety.DISCLAIMER
        ),
    )
    async def janus_modelkit_search(
        query: Annotated[
            str,
            StringConstraints(strip_whitespace=True, to_lower=True, min_length=1, max_length=32),
        ]
        | None = None,
    ) -> dict[str, Any]:
        path = "/modelkit/drugs?limit=50" + (f"&q={quote(query)}" if query else "")
        payload = await api("GET", path)
        if query and isinstance(payload, dict):
            obj = cast(dict[str, Any], payload)
            raw = obj.get("drugs")
            drugs = cast(list[Any], raw) if isinstance(raw, list) else []
            dicts = [cast(dict[str, Any], d) for d in drugs if isinstance(d, dict)]
            kept: list[dict[str, Any]] = [d for d in dicts if query in str(d.get("key", ""))]
            payload = {**obj, "drugs": kept}
        return result(payload, *safety.MODELKIT_LINES)

    @server.tool(
        annotations=READ_ONLY,
        description=(
            "One drug of the experimental model kit (Janus GET /modelkit/drugs/{key}): the "
            "parameter set with confidence classes and evidence ids, the validation report, what "
            "was left out and the special-population statements (older adults, renal and hepatic "
            "impairment) quoted from US labels; `key` comes from janus_modelkit_search. Research "
            "use only. " + safety.DISCLAIMER
        ),
    )
    async def janus_modelkit_get(
        key: Annotated[str, Field(pattern=DRUG_KEY)],
    ) -> dict[str, Any]:
        payload = await api("GET", f"/modelkit/drugs/{key}")
        return result(payload, *safety.MODELKIT_LINES)

    @server.tool(
        annotations=READ_ONLY,
        description=(
            "The evidence rows behind one drug of the experimental model kit (Janus GET "
            "/modelkit/drugs/{key}/evidence): every value (ClinicalTrials.gov results, US labels, Drugs@FDA review "
            "PDFs, PubMed Central articles licensed CC BY or CC0) with its quoted source text, locator, "
            "formulation, route, both automated reader verdicts, whether it built the set, tested "
            "it or was left out and why. `key` comes from janus_modelkit_search; `parameter` "
            "(for example cmax or auc_inf) and `role` (building, validation, excluded) keep only "
            "those rows. Research use only. " + safety.DISCLAIMER
        ),
    )
    async def janus_modelkit_evidence(
        key: Annotated[str, Field(pattern=DRUG_KEY)],
        parameter: Annotated[str, Field(pattern=PARAMETER)] | None = None,
        role: Literal["building", "validation", "excluded"] | None = None,
    ) -> dict[str, Any]:
        payload = await api("GET", f"/modelkit/drugs/{key}/evidence")
        if (parameter or role) and isinstance(payload, dict):
            obj = cast(dict[str, Any], payload)
            raw = obj.get("rows")
            rows = cast(list[Any], raw) if isinstance(raw, list) else []
            dicts = [cast(dict[str, Any], r) for r in rows if isinstance(r, dict)]
            kept: list[dict[str, Any]] = [
                r
                for r in dicts
                if (not parameter or r.get("parameter") == parameter)
                and (not role or r.get("role") == role)
            ]
            payload = {**obj, "rows": kept}
        return result(payload, *safety.MODELKIT_LINES)

    return server


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="janus-mcp", description=safety.DISCLAIMER)
    ap.add_argument("--transport", choices=["stdio", "streamable-http"], default="stdio")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args(argv)
    if args.host not in LOOPBACK:
        # No MCP authorization yet: the HTTP transport is for this computer only (safety review S9).
        print("janus-mcp: --host must be 127.0.0.1, localhost or ::1", file=sys.stderr)
        return 2
    try:
        config = from_env()
    except ConfigError as exc:
        print(f"janus-mcp: {exc}", file=sys.stderr)
        return 2
    server = build_server(config)
    if args.transport == "stdio":
        server.run("stdio")
    else:
        server.run("streamable-http", host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
