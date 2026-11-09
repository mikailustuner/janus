# Requirements: Deploy (Phase 5)

> Written 2026-11-09. Owner decisions of 2026-11-09:
> - Host: one existing Linux arm64 VM of the owner in an EU cloud region (GDPR: donated data stays in
>   the EU), running Docker. Host details (name, provider account, addresses, other services) are kept
>   out of this public repository, in the owner's private notes.
> - Domain: `janusmeds.org`, DNS on Cloudflare Free.
> - The other services on the Host are private (reachable only over the owner's private network).
>   **Janus is the first public service on the Host**; it must not weaken that.
> - Public ingress through a **locally managed Cloudflare Tunnel** (created with
>   `cloudflared tunnel login` / `tunnel create`; no Zero Trust dashboard, no paid plan).
> - Donations and the outcome loop start **off** (no health data is stored on the server at launch;
>   the consent texts are pending expert and legal review, see `docs/pre-launch-checklist.md`).

## Introduction
Judges must reach a working Janus at a public URL from submission until the end of judging
(2027-01-29, official rules). The deploy puts the existing web and API images on the Host behind
`janusmeds.org`, isolated from the other services on the same host, with no inbound port opened.

## Glossary
- **Host:** the owner's server (see the note above).
- **Stack:** the Janus Docker Compose project on the Host (in a directory called `STACK_DIR` below).
- **Edge network:** the Docker network shared by `cloudflared` and `web` only.
- **Internal network:** a Docker network with `internal: true` (no route out) for `web`, `api`, `postgres`.
- **Other services:** everything on the Host that is not part of the Stack, the Host's own ports,
  the owner's private network and the cloud metadata service.
- **Runtime data:** the read-only data the API serves (FAERS counts, resolution tables, cascades,
  light face, time machine, evidence), built by `pipelines/`.

## Requirement 1: Public entry point
**User story:** As a judge, I want to open `https://janusmeds.org` and use Janus, so that I can test it.
1. THE Stack SHALL serve the web app at `https://janusmeds.org` through a Cloudflare Tunnel whose only
   ingress rule maps `janusmeds.org` to `http://web:3000` and whose catch-all rule returns 404.
2. THE Host SHALL NOT open any new inbound port for Janus (no change to the cloud firewall, no
   public `ports:` mapping in the Stack).
3. THE API SHALL NOT have a public hostname; the browser reaches it only through the web app's
   same-origin `/api/*` rewrite (experience DP15).
4. WHEN a request uses plain HTTP, THE edge SHALL redirect it to HTTPS (Cloudflare "Always Use HTTPS").
5. `www.janusmeds.org` SHALL redirect to `https://janusmeds.org` (or not resolve); it SHALL NOT serve a second copy.

## Requirement 2: Isolation from the other services
**User story:** As the server owner, I want a fault in Janus to stay inside Janus, so that my private services stay private.
1. THE `api` and `postgres` containers SHALL be attached only to the Internal network.
2. THE `web` container SHALL be attached to the Internal and Edge networks; `cloudflared` only to the Edge network.
3. WHILE the Stack runs, a container of the Stack SHALL NOT reach: any port of the Host, any other
   Docker network, the private ranges (RFC 1918 and RFC 6598) outside its own networks, or
   the metadata service `169.254.169.254` (host firewall rules, design §4).
4. THE Stack SHALL NOT use `network_mode: host`, the Docker socket, `privileged`, added capabilities or host bind mounts other than the read-only Runtime data and the tunnel credentials.
5. EVERY container SHALL run as a non-root user with `no-new-privileges`, a read-only root file
   system (tmpfs where a writable path is needed), and memory and CPU limits.
6. A verification script SHALL prove 2.3 from inside each container after every deploy.

## Requirement 3: Secrets
1. Secrets (Postgres password, noise key, tunnel credentials) SHALL exist only on the Host, in files owned by the deploy user with mode 600.
2. Secrets SHALL NOT appear in git, in image layers, in logs, in this repository's documents, or in any message to the developer's assistant.
3. Note signing keys SHALL NOT be configured while the outcome loop is off.

## Requirement 4: Privacy at launch
1. THE API SHALL start with donations disabled (`JANUS_DONATION_REGION` empty) and the outcome loop disabled (no note keys).
2. WHEN donations or the outcome loop are disabled, THE web app SHALL show its existing "not available" states and never a broken form.
3. THE Stack SHALL keep the existing log rules (privacy.md): no access logs, no request bodies, Postgres terse logging.
4. Cloudflare analytics that are collected by default SHALL be documented on the privacy page; no extra tracking (no Web Analytics beacon, no cookies).
5. Enabling donations or the outcome loop later SHALL require a new owner decision and the consent review on the pre-launch checklist.

## Requirement 5: Data on the Host
1. THE Runtime data SHALL be mounted read-only into `api`.
2. TİTCK-derived data SHALL be fetched by the `titck` pipeline job on the Host (data-sources.md: "do not commit; fetch at runtime"); it SHALL NOT be copied from the developer's PC.
3. Other Runtime data (CC0, CC BY, licence ouverte) MAY be built on the developer's PC and copied to the Host over the owner's private network; every copy keeps its run id and licence file.
4. A refresh SHALL switch the `current` link atomically, so the API never reads a half-copied run.

## Requirement 6: Build and release
1. Images SHALL be built on the Host (native arm64) from a git commit of the public repository; the deployed commit id SHALL be visible at `/health`.
2. A deploy SHALL run Alembic migrations (forward-only) before the new API starts.
3. A failed deploy SHALL leave the previous version running (build first, then swap).
4. A rollback to the previous commit SHALL take one command.

## Requirement 7: Availability until the end of judging
1. All Stack services SHALL restart automatically after a crash or a Host reboot.
2. An uptime check run by the owner (outside the Stack) SHALL request `/health` and the demo page every 5 minutes and alert the owner.
3. The domain SHALL auto-renew and the Stack SHALL stay up until at least 2027-01-31.
4. THE Stack SHALL stay within 4 GB of memory and 2 CPUs in total, so the Other services keep their resources.

## Requirement 8: Verification
1. After a deploy, a smoke test SHALL pass from the public internet: home, demo, results, passport, time machine, open data, privacy page in `en` and `tr`; `/api/health`; security headers (CSP, no-referrer) present.
2. THE Playwright e2e suite (en + tr) SHALL pass against `https://janusmeds.org` in demo mode.
3. An external port scan of the Host's public IP SHALL show no port other than those open before the deploy.
