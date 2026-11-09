# Design: Deploy (Phase 5)

## 1. Overview
```
browser ──HTTPS──▶ Cloudflare edge ──(outbound tunnel)──▶ cloudflared ──▶ web:3000 ──/api/*──▶ api:8000 ──▶ postgres:5432
                                                     [ janus-edge ]      [ janus-edge + janus-internal ]  [ janus-internal (internal: true) ]
```
Everything lives in one directory on the Host (`STACK_DIR`), as one Compose project named `janus`.

## 2. Layout on the Host
```
STACK_DIR/
  compose.yml            # from deploy/compose.yml in the repo
  .env                   # secrets, mode 600 (POSTGRES_PASSWORD, JANUS_NOISE_KEY)
  src/                   # git worktree of the public repo at the deployed commit
  cloudflared/           # cert.pem, <tunnel-id>.json, config.yml; mode 600 / 700
  data/                  # Runtime data (read-only mount), runs + `current` links
  releases.log           # deployed commit ids, newest last
```
The repository gets `deploy/` with `compose.yml`, `cloudflared.config.yml.example`,
`deploy.sh`, `rollback.sh`, `verify-isolation.sh`, `firewall.sh` (run by the owner with sudo),
`smoke.sh` and `README.md`. No secret and no host-specific value is committed.

## 3. Compose (design decisions)
| DP | Decision | Why |
|---|---|---|
| DP1 | Two networks: `janus-edge` (bridge, fixed subnet `172.31.250.0/24`) and `janus-internal` (`internal: true`, `172.31.251.0/24`) | Fixed subnets make the firewall rules exact; `internal` gives api and postgres no route out at all |
| DP2 | No `ports:` anywhere | Req 1.2: nothing listens on the Host |
| DP3 | `cloudflared` image pinned by version, `tunnel --no-autoupdate run janus`, config and credentials mounted read-only | Locally managed tunnel (owner decision), no dashboard |
| DP4 | Every service: `user` non-root, `read_only: true`, `tmpfs` for `/tmp` (web also `/app/apps/web/.next/cache`), `security_opt: [no-new-privileges:true]`, `cap_drop: [ALL]`, `mem_limit`, `cpus`, `restart: unless-stopped`, `pids_limit` | Req 2.5, 7.1 |
| DP5 | Limits: postgres 768 MB / 0.5, api 1.5 GB / 1.0, web 768 MB / 0.5, cloudflared 128 MB / 0.25 (total ≈ 3.2 GB / 2.25) | Req 7.4; leaves the Host's other services their resources |
| DP6 | Postgres keeps the dev compose's terse logging flags; data in a named volume | privacy.md |
| DP7 | Images built on the Host with `docker compose build` from `src/` at a commit; tag `janus-api:<commit>`, `janus-web:<commit>` | Native arm64, no registry, no cross-build; Req 6.1 |
| DP8 | `JANUS_PUBLIC_BASE_URL=https://janusmeds.org` (24 bytes ≤ 40) | QR size rule (doctor-loop §6.6) |
| DP9 | Donations and outcome loop off: `JANUS_DONATION_REGION`, `JANUS_CONSENT_VERSIONS`, `JANUS_NOTE_KEYS` unset; `JANUS_NOISE_KEY` set anyway (open-data release refuses to run without it) | Req 4.1, owner decision |
| DP10 | `/health` returns `{"status":"ok","commit":"<12 hex>"}` from a build arg `JANUS_COMMIT` (web shows it nowhere) | Req 6.1 |

## 4. Isolation firewall (owner runs `deploy/firewall.sh` with sudo)
Docker's bridge traffic to the Host itself goes through `INPUT`; traffic to other networks through
`FORWARD` (`DOCKER-USER`). With `br_netfilter`, traffic between containers of one bridge also passes
`DOCKER-USER`, so own-subnet traffic is accepted first.
```
# INPUT: no Stack container may open a connection to the Host
iptables -I INPUT -s 172.31.250.0/24 -m conntrack --ctstate NEW -j DROP
iptables -I INPUT -s 172.31.251.0/24 -m conntrack --ctstate NEW -j DROP
# DOCKER-USER: own subnets allowed, private, shared-address (RFC 6598) and metadata ranges dropped, internet allowed (edge only)
iptables -I DOCKER-USER 1 -s 172.31.250.0/24 -d 172.31.250.0/24 -j RETURN
iptables -I DOCKER-USER 2 -s 172.31.251.0/24 -d 172.31.251.0/24 -j RETURN
for net in 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16 100.64.0.0/10 169.254.0.0/16; do
  iptables -I DOCKER-USER 3 -s 172.31.250.0/24 -d $net -j DROP
  iptables -I DOCKER-USER 3 -s 172.31.251.0/24 -d $net -j DROP
done
```
The same rules for `ip6tables` are not needed while Docker IPv6 is off (checked by the script).
Persistence: a small `janus-firewall.service` (oneshot, `After=docker.service`) that runs the script;
the script is idempotent (it deletes its own rules by comment `janus-isolation` before inserting).
The owner reviews the script before running it. The assistant never runs sudo.

`verify-isolation.sh` runs `docker compose exec` probes (busybox `nc -z -w2` from a throw-away
container attached to each network, so the app images need no tools): every listening port of the
Host gateway (read at run time with `ss -tln`, never committed); an address of the owner's private
network (from a host-local file); `169.254.169.254:80`; another Docker network's gateway — all must
fail; `web → api:8000` and `api → postgres:5432` must succeed; `cloudflared → region1.v2.argotunnel.com:7844` must succeed.

## 5. Runtime data
- `deploy/sync-data.sh` (PC side) copies the built runs of `faers`, `faers_counts`, `us_ndc`,
  `eu_fr_bdpm`, `eu_es_cima`, `wikidata_ingredients`, `pipc`, `onsides`, `openfda_label`,
  `retractions`, `canon`, `canon_gold`, `tm_*`, `faers_onset`, light face, time machine and cascades
  with `rsync` over the owner's private network into `data/<job>/runs/<run-id>/`, then flips `current` with
  `ln -sfn` + `mv -T` (atomic rename). Never `titck` (Req 5.2). ≈ 200 MB.
- The TİTCK list is fetched on the Host by a one-off `pipelines` container on a third network
  `janus-jobs` (egress allowed, same DOCKER-USER drops), writing to `data/titck/`. Weekly refresh by a
  user systemd timer. The API image never fetches.

## 6. Release flow (`deploy.sh <commit>`)
1. `git -C src fetch && git -C src checkout --detach <commit>`; refuse a dirty tree.
2. Build `janus-api:<commit>` and `janus-web:<commit>` (`JANUS_COMMIT` build arg). On failure: stop, nothing changed.
3. `docker compose run --rm migrate` with the new API image.
4. `JANUS_TAG=<commit> docker compose up -d --wait` (healthchecks gate the swap).
5. `verify-isolation.sh` and `smoke.sh http://web:3000` from inside the edge network; on failure,
   `rollback.sh` (re-up with the previous tag from `releases.log`). Migrations are forward-only and
   backward-compatible within one release (existing rule), so rollback needs no downgrade.
6. Append the commit to `releases.log`; keep the last 3 image tags, prune older ones.

## 7. Cloudflare settings (owner, in the free dashboard)
SSL/TLS **Full (strict)** is not needed for a tunnel (the edge→origin leg is the tunnel itself); set
**Full** and **Always Use HTTPS**, **Min TLS 1.2**, HSTS off until the domain is stable (then 6 months),
Web Analytics **off**, Bot Fight Mode on, one free rate-limiting rule on `/api/*` (100 req / 10 s per IP).
`cloudflared tunnel route dns janus janusmeds.org` creates the proxied CNAME.

## 8. Monitoring
A check run by the owner outside the Stack (a scheduled job on a private machine) requests
`https://janusmeds.org/api/health` and `/en/demo` every 5 minutes and notifies the owner on two
failures in a row. No health data in the check.

## 9. Properties / checks
| # | Check | Req |
|---|---|---|
| C1 | `docker compose config` has no `ports`, no `network_mode: host`, no `privileged`, every service has `read_only`, `user`, `cap_drop: [ALL]`, limits (unit test on the YAML) | 1.2, 2.4, 2.5 |
| C2 | `verify-isolation.sh` all expected-fail probes fail, expected-pass probes pass | 2.3 |
| C3 | `git ls-files deploy` contains no secret pattern; `cloudflared` dir and `.env` are never in the repo | 3.2 |
| C4 | `/api/health` commit equals the deployed commit | 6.1 |
| C5 | `smoke.sh` + Playwright en/tr against the public URL | 8.1, 8.2 |
| C6 | `nmap -Pn` of the public IP before and after: same open ports | 8.3 |
| C7 | API logs after the smoke test contain no route parameters or bodies (log-guard regex) | 4.3 |

## 10. Open items
- Host hardening outside Janus is tracked in the owner's private notes, not here.
- Privacy page: add a sentence on Cloudflare as the network provider (Req 4.4), five languages.
