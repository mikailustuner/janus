# Releasing

Every deployment of the public site is a tagged release.

1. Add a section `## [X.Y.Z] - YYYY-MM-DD` to [CHANGELOG.md](../CHANGELOG.md) (move the items from
   "Unreleased"), merge to `main`, push, and wait for CI and the security scans to pass.
2. `scripts/release.sh X.Y.Z` sets the version and date in `CITATION.cff`, commits that, creates the annotated tag
   `vX.Y.Z` and pushes it. With the Zenodo integration enabled, the tag gets a DOI.
3. On the server, `deploy/deploy.sh <commit of the tag>` builds, migrates, swaps and checks; the server's
   `releases.log` then records the first 12 characters of that commit, so every entry maps to a tag.

Version numbers follow Semantic Versioning. Below 1.0 a minor version may change public API answers; such changes
are listed under "Changed" in the changelog.
