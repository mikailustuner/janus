"""Route kinds (privacy design §4.3, DP2).

Every route is medical unless it is operational and on `OPERATIONAL_ALLOWLIST`. Routers are
made with `medical_router()`, `donation_router()` or `operational_router()`; `classify(app)`
fails at startup when a route has no kind or an operational route is not on the allowlist.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, ClassVar, Final

from fastapi import APIRouter, FastAPI
from fastapi.routing import APIRoute
from starlette.routing import BaseRoute, Route

OPERATIONAL_ALLOWLIST: Final = frozenset(
    {
        "/health",
        "/privacy/storage",
        "/memory/snapshot",
        "/openapi.json",
        "/docs",
        "/docs/oauth2-redirect",
        "/redoc",
    }
)


class RouteKind(StrEnum):
    operational = "operational"
    medical = "medical"
    donation = "donation"


class KindRoute(APIRoute):
    kind: ClassVar[RouteKind | None] = None


class OperationalRoute(KindRoute):
    kind = RouteKind.operational


class MedicalRoute(KindRoute):
    kind = RouteKind.medical


class DonationRoute(KindRoute):
    kind = RouteKind.donation


def operational_router(**kwargs: Any) -> APIRouter:
    return APIRouter(route_class=OperationalRoute, **kwargs)


def medical_router(**kwargs: Any) -> APIRouter:
    return APIRouter(route_class=MedicalRoute, **kwargs)


def donation_router(**kwargs: Any) -> APIRouter:
    return APIRouter(route_class=DonationRoute, **kwargs)


def route_kind(route: object) -> RouteKind:
    """Kind of a matched route; anything unknown counts as medical (fail-safe)."""
    if isinstance(route, KindRoute) and route.kind is not None:
        return route.kind
    if isinstance(route, Route) and not isinstance(route, APIRoute):
        if route.path in OPERATIONAL_ALLOWLIST:
            return RouteKind.operational
    return RouteKind.medical


class RouteClassificationError(RuntimeError):
    pass


def _check(path: str, kind: RouteKind | None, kinds: dict[str, RouteKind]) -> None:
    if kind is None:
        raise RouteClassificationError(f"route {path} has no kind (use a policy router)")
    if kind is RouteKind.operational and path not in OPERATIONAL_ALLOWLIST:
        raise RouteClassificationError(f"operational route {path} is not on the allowlist")
    kinds[path] = kind


def classify(app: FastAPI, routers: list[APIRouter]) -> dict[str, RouteKind]:
    """Check every route has a kind; return template -> kind. Raises on a violation.

    FastAPI 0.162 includes routers lazily, so the routes come from `routers` (the routers the
    app includes). Prefixes are forbidden so that a matched route's `path` is its full template.
    """
    kinds: dict[str, RouteKind] = {}
    for router in routers:
        if router.prefix:
            raise RouteClassificationError("policy routers must not use a prefix")
        for route in router.routes:
            if not isinstance(route, KindRoute):
                raise RouteClassificationError("router contains an unclassified or nested route")
            _check(route.path, route.kind, kinds)
    included = {id(r) for r in routers}
    app_routes: list[BaseRoute] = list(app.routes)
    for route in app_routes:
        if isinstance(route, KindRoute):
            _check(route.path, route.kind, kinds)
        elif isinstance(route, APIRoute):
            raise RouteClassificationError(f"route {route.path} has no kind (use a policy router)")
        elif isinstance(route, Route) and route.path in OPERATIONAL_ALLOWLIST:
            kinds[route.path] = RouteKind.operational
        elif id(getattr(route, "original_router", None)) in included:
            continue
        else:
            raise RouteClassificationError("app contains a route that is not classified")
    return kinds
