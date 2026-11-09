"""Response models for `/timemachine/*` — the web contract (design §10).

Read-only, stateless, precomputed. Every response carries the disclaimer and the review status;
numeric fields carry their unit in the field name. Codes the web app translates are listed in
design §10.3; the API never sends a user-facing sentence in any language.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Meta(Base):
    built_at: str
    review_status: Literal["Expert review has not yet been done"]
    disclaimer: str
    seed: int
    simulations: int


class CatalogueOut(Base):
    meta: Meta
    substance_ids: list[str]
    cascade_ids: list[str]
    validation: dict[str, Any]
    sources: dict[str, Any]
    onset_subset_caveat: str


class SubstanceOut(Base):
    meta: Meta
    substance: dict[str, Any]
    exposure: list[dict[str, Any]]
    references: list[dict[str, Any]]


class CascadeOut(Base):
    meta: Meta
    cascade: dict[str, Any]
    faers_quality: dict[str, Any]
    onset_subset_caveat: str
    references: list[dict[str, Any]]
