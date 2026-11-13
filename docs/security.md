# Security

How the public Janus is protected, what is checked automatically, and what risks remain. Host-specific
details (addresses, names, paths) are deliberately not in this repository. Deployment: [deploy/README.md](../deploy/README.md).

## What there is to protect

- **No health data on the server.** Medication lists stay in the browser; the doctor outcome loop and
  donations are off in the public deployment, so the database holds reference data, the anonymous
  simulation queue and nothing about a person.
- **Integrity of what the site shows**: reference data, evidence links, the cascade rule base, model kit
  values. A tampered value could mislead a reader.
- **Availability** of a free public service.
- **Secrets**: the database passwords and the key for the noise added to shared counts.

## Trust boundaries

```
browser ─HTTPS─▶ CDN/WAF ─outbound tunnel─▶ web ─/api/*─▶ api ─▶ postgres ◀─ simulator
                                            [edge]       [internal network, no route out]
```

The server publishes no port; the tunnel connects outwards. `api`, `postgres` and `simulator` sit on an
internal Docker network without a route to the internet, other networks, the host or the cloud metadata
service (host firewall rules, checked by `deploy/verify-isolation.sh` at every release).

## Threats and controls

| Threat | Controls |
| --- | --- |
| Injection (SQL, command) | Parameterised queries only; strict request models (`extra="forbid"`, typed fields, length limits); no shell calls with request data |
| Cross-site scripting, clickjacking, downgrade | Content-Security-Policy (no inline objects, `frame-ancestors 'none'`), `X-Content-Type-Options`, `Referrer-Policy`, `Strict-Transport-Security`; React escaping; checked by `deploy/smoke.sh` |
| Server-side request forgery, data exfiltration | Containers cannot open connections out (internal network, host firewall); the simulator reads and writes only its queue table with its own database role |
| Abuse and denial of service | CDN rate limiting; in-app limits (keyed hashes, never addresses); request body limits per path; simulation queue caps (2 slots, 10 queued, 30 s per job); CPU and memory limits per container |
| Container escape, privilege | Non-root users, read-only root file systems, no capabilities, `no-new-privileges`; `deploy/check_compose.py` enforces these in CI |
| Supply chain | Lock files (`uv.lock`, `pnpm-lock.yaml`); pinned base images and tool versions; dependency, secret and image scans in CI; Dependabot; CodeQL |
| Leaked secrets | Secrets generated on the server, never in the repository, and mounted into the containers as files readable only by the one container user that needs each (never environment variables, so `docker inspect` shows none); every release is first run on an ephemeral staging stack with a copy of the database; secret scanning of the full history in CI and of staged changes before each commit (`.gitleaks.toml`) |
| Privacy leaks through logs and metrics | No access logs; Postgres logs no statements or row values; metrics carry fixed labels only and are served on a private port (`docs/metrics.md`) |
| Loss of data | Daily database dump and weekly data snapshot pulled by a separate machine that the server cannot reach; restore tested (`deploy/README.md`, "Backups") |
| Tampered or stale reference data | Every artifact carries a manifest with content hashes, source URL, licence and snapshot date; the integrity check marks retracted or corrected sources |

## Automated checks

| Check | Where | Gate |
| --- | --- | --- |
| `pip-audit` on the locked Python dependencies (API, MCP server, pipelines) | `.github/workflows/security.yml` | no known vulnerability |
| `pnpm audit` | same | none of high or critical severity |
| gitleaks, full git history | same, and the pre-commit hook for staged changes | no finding |
| Trivy on the API, web and simulator images, CycloneDX SBOM of each | same | no fixable high or critical finding |
| CodeQL (Python, TypeScript) | `.github/workflows/codeql.yml` | alerts reviewed in code scanning |
| Container hardening rules | `deploy/check_compose.py` in CI | every rule holds |
| Network isolation, headers, deployed commit | `deploy/verify-isolation.sh`, `deploy/smoke.sh` at every release | all probes pass, else roll back |

Images apply the distribution's security updates at build time; the web runtime image carries no package
manager.

## Known gaps

- The CDS Hooks service has no client authentication yet and is meant for sandboxes only.
- One server; a host failure means downtime until it is restored from backup.
- The CDN and tunnel provider is a dependency outside this project's control.

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting for this repository
(Security → Report a vulnerability). Do not open a public issue for a vulnerability, and do not include
personal or patient data in any report.
