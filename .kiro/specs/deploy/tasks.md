# Tasks: Deploy (Phase 5)

Owner actions are marked **[owner]**; the assistant never runs sudo and never reads secrets.

- [ ] 1. Repository: `deploy/compose.yml` (DP1–DP9), `deploy/README.md`, `JANUS_COMMIT` in both
  Dockerfiles and `/health` (DP10); unit test for C1 on the compose file. _Req 1.2, 2.1–2.5, 6.1_
- [ ] 2. Scripts: `deploy.sh`, `rollback.sh`, `verify-isolation.sh`, `smoke.sh`, `sync-data.sh`,
  `firewall.sh` + `janus-firewall.service`; shellcheck in CI; C3. _Req 2.3, 2.6, 5.3–5.4, 6.2–6.4_
- [ ] 3. Privacy page: Cloudflare as network provider, five languages, translation and safety review. _Req 4.4_
- [ ] 4. Checkpoint: CI green; owner reviews `firewall.sh` and the compose file.
- [ ] 5. **[owner]** `janusmeds.org` active on Cloudflare; Cloudflare settings of design §7.
- [ ] 6. Host: create `STACK_DIR`, clone `src/`, `cloudflared tunnel login` (owner opens the
  link and authorises the zone), `tunnel create janus`, `route dns`, write `config.yml` (one ingress rule + 404). _Req 1.1, 1.3_
- [ ] 7. **[owner]** create `STACK_DIR/.env` (mode 600) from `deploy/env.example`; run `sudo deploy/firewall.sh` and enable `janus-firewall.service`. _Req 2.3, 3.1_
- [ ] 8. Data: `sync-data.sh` from the PC; `titck` job on the Host. _Req 5_
- [ ] 9. First deploy: `deploy.sh <commit>`; C2, C4, C7; port scan C6 (before snapshot taken in task 6). _Req 6, 8.3_
- [ ] 10. Public verification: `smoke.sh https://janusmeds.org`, Playwright en + tr against the URL (C5). _Req 8.1, 8.2_
- [ ] 11. Monitoring (design §8) and the weekly TİTCK timer. _Req 7.2, 5.2_
- [ ] 12. Docs: README "Try it" link, Devpost testing instructions draft, `docs/pre-launch-checklist.md`
  (deploy items), Kiro usage log entry. Final checkpoint with the owner.
