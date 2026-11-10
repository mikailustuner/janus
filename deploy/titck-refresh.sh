#!/usr/bin/env bash
# Fetch the TİTCK list on the server (deploy Req 5.2) with the pipelines image, refresh the open
# Canadian and Italian product lists, then reload the resolution tables. Weekly by
# janus-titck.timer. The job runs on its own network with internet access; the host firewall
# rules apply to it too (design §5).
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
docker network inspect janus-public-jobs >/dev/null 2>&1 \
  || docker network create --subnet 172.31.252.0/24 janus-public-jobs >/dev/null
docker build --quiet -t janus-pipelines:local -f "$DEPLOY_DIR/pipelines.Dockerfile" "$SRC_DIR/pipelines" >/dev/null
mkdir -p "$STACK_DIR/data"
docker run --rm --network janus-public-jobs --user "$(id -u):$(id -g)" --read-only --tmpfs /tmp \
  --cap-drop ALL --security-opt no-new-privileges:true \
  -e HOME=/tmp -e JANUS_DATA_DIR=/data -v "$STACK_DIR/data:/data" janus-pipelines:local run titck
# Open national product lists (national-products Req 8.2: Health Canada DPD, AIFA open data),
# fetched before the reload so that one load covers them. A failed or held refresh keeps the
# previous run and does not stop the rest of this job.
for job in ca_dpd eu_it_aifa; do
  docker run --rm --network janus-public-jobs --user "$(id -u):$(id -g)" --read-only --tmpfs /tmp \
    --cap-drop ALL --security-opt no-new-privileges:true \
    -e HOME=/tmp -e JANUS_DATA_DIR=/data -v "$STACK_DIR/data:/data" janus-pipelines:local run "$job" \
    || log "$job not refreshed; the previous run stays current"
done
"$DEPLOY_DIR/load-data.sh"
# Weekly FDA recall records (recall-check Req 7.2): the running API reads the new run by itself.
# A failed or held refresh keeps the previous run and does not stop the rest of this job.
docker run --rm --network janus-public-jobs --user "$(id -u):$(id -g)" --read-only --tmpfs /tmp \
  --cap-drop ALL --security-opt no-new-privileges:true \
  -e HOME=/tmp -e JANUS_DATA_DIR=/data -v "$STACK_DIR/data:/data" janus-pipelines:local run us_recalls \
  || log "recall records not refreshed; the previous run stays current"
# Weekly data-quality report (data-quality spec): compares the fresh TİTCK run with the other
# sources and moves `quality/current`; the running API picks it up. No --publish on the server:
# the committed open copy is updated from the repository, not from here.
tag="${JANUS_TAG:-$(current_tag)}"
docker run --rm --network none --user "$(id -u):$(id -g)" --read-only --tmpfs /tmp \
  --cap-drop ALL --security-opt no-new-privileges:true \
  -e HOME=/tmp -e JANUS_DATA_DIR=/data -v "$STACK_DIR/data:/data" \
  "janus-api:$tag" python -m janus.quality.build --data-dir /data
log "data-quality report rebuilt"
