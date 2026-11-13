# Releasing

Every deployment of the public site is a tagged release.

1. Run the full browser suite on a developer machine (CI runs only `smoke` and `routes`; the rest needs the OCR
   models): `pnpm --filter @janus/web build && pnpm --filter @janus/web exec playwright test --workers=2`. Every spec
   must pass; a stale expectation is fixed in the spec, a real defect in the code.
2. Add a section `## [X.Y.Z] - YYYY-MM-DD` to [CHANGELOG.md](../CHANGELOG.md) (move the items from
   "Unreleased"), merge to `main`, push, and wait for CI and the security scans to pass.
3. `scripts/release.sh X.Y.Z` sets the version and date in `CITATION.cff`, regenerates the site's validation file from it, commits both, creates the annotated tag
   `vX.Y.Z` and pushes it. With the Zenodo integration enabled, the tag gets a DOI.
4. On the server, `deploy/deploy.sh <commit of the tag>` builds, migrates, swaps and checks; the server's
   `releases.log` then records the first 12 characters of that commit, so every entry maps to a tag.

Version numbers follow Semantic Versioning. Below 1.0 a minor version may change public API answers; such changes
are listed under "Changed" in the changelog.
