import os

from hypothesis import HealthCheck, settings

settings.register_profile("dev", max_examples=100, deadline=None)
settings.register_profile(
    "ci",
    max_examples=300,
    deadline=None,
    derandomize=True,
    suppress_health_check=[HealthCheck.too_slow],
)
# Nightly: random seeds and more examples; a failure prints its blob, then pin it with @example.
settings.register_profile(
    "nightly",
    max_examples=1000,
    deadline=None,
    print_blob=True,
    suppress_health_check=[HealthCheck.too_slow],
)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "dev"))
