"""Hypothesis profiles: `dev` locally, `ci` (derandomized) in CI, `nightly` (random seeds)."""

from __future__ import annotations

import os

from hypothesis import settings

settings.register_profile("dev", deadline=None)
settings.register_profile("ci", deadline=None, derandomize=True)
settings.register_profile("nightly", max_examples=1000, deadline=None, print_blob=True)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "dev"))
