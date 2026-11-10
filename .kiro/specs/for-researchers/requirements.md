# Requirements: Janus for researchers

> Owner request 2026-11-10: the research tools exist but are scattered (open data, public API, MCP server, CDS Hooks
> service, pipelines, research notes). One page tells a researcher, in one place, what exists and how to start in
> ten minutes. It describes only what exists in the repository. Everything here is researcher-facing; nothing is
> guidance for a person. Research prototype, not a medical device. Expert review has not yet been done.

## Requirement 1: One page, one markdown twin
1. THE web app SHALL serve `/[locale]/research/for-researchers` in en, tr, de, fr and es, in both themes.
2. THE repository SHALL contain `docs/for-researchers.md` with the same content in English, linked from the README.
3. THE page SHALL be linked from the Research index and from the footer; the Open data page SHALL link to it.

## Requirement 2: Content (inventory-backed)
1. THE page SHALL open with a ten-minute path: pick a source, run one request, run the worked example, read the limits.
2. THE page SHALL list the open data files (`data/open/*`), each with its licence, version and how to cite.
3. THE page SHALL list the public read-only API routes with one request each and the rate limits stated in the
   repository (simulation: 3 submissions per 30 s and 5 per 10 min per client, 120 polls per minute; the read-only
   open-data routes state none, so the page asks for gentle use).
4. THE page SHALL describe the MCP server (seven tools, read-only for the research routes, how to run it, the Kiro
   settings example), the CDS Hooks service (discovery URL, hooks, sandbox only, no client authentication yet) and the
   pipelines (how to run one job, `sources.toml`, `NOTICE`).
5. THE page SHALL link the two research notes with the status "Expert review has not yet been done".
6. THE page SHALL contain one worked example that was run against a real API before it was written down, and the
   same code SHALL be in `docs/examples/onset_summary.py`.
7. THE page SHALL describe nothing that does not exist in the repository.

## Requirement 3: Limitations, reporting, citing
1. THE page SHALL state the limits: counts are reports not people, FAERS is spontaneous and not deduplicated,
   descriptive not causal, not incidence, no start dates in CDS Hooks, expert review has not yet been done.
2. THE page SHALL link the GitHub issues page for errors and `docs/contributing-corrections.md`.
3. THE page SHALL give a citation built only from information already in the repository (the copyright holder named
   in `NOTICE`, the repository URL, the dataset version strings). THE repository has no `CITATION.cff`; see Open
   items: the owner decides the citation metadata.

## Requirement 4: Wording and safety
1. THE page SHALL say "automated", never "AI", and SHALL NOT imply review by a person.
2. THE page SHALL NOT name server details, unpublished material or any TİTCK product row; the only
   host is `https://janusmeds.org`.
3. THE page SHALL pass the forbidden-phrase lists of all five languages.

## Requirement 5: Interface
1. Code blocks SHALL have a copy button (the existing `Developers` snippet component), a keyboard-focusable scroll
   area and no page-level horizontal scroll at 375 px.
2. THE page SHALL meet WCAG 2.2 AA (axe), 44 px targets and the disclaimer on the page.

## Open items for the owner
- No `CITATION.cff` exists. Proposal: add one with the title "Janus", the repository URL, licence Apache-2.0 and the
  author name as in `NOTICE`, plus ORCID and a DOI (for example through a Zenodo release) if the owner wants them.
  Not created here, because authorship metadata is the owner's decision.
- The public site refuses the default Python `User-Agent` (HTTP 403); the example sends its own.
