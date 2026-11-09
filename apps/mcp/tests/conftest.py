"""Hypothesis profiles: `dev` locally, `ci` (derandomized) in CI."""

from __future__ import annotations

import os

from hypothesis import settings

settings.register_profile("dev", deadline=None)
settings.register_profile("ci", deadline=None, derandomize=True)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "dev"))
