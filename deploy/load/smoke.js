// Small load check of the public API (docs/operations.md, plan C5): three users for 30 s read the health
// and model kit routes and queue one small simulation each, then read its result. Not a stress test; the
// simulation route is rate limited, so a 429 counts as a correct answer.
//   docker run --rm -i grafana/k6:1.0.0 run -e BASE=https://janusmeds.org - < deploy/load/smoke.js
import http from "k6/http";
import { check, sleep } from "k6";

const BASE = __ENV.BASE || "https://janusmeds.org";
const JOB = JSON.stringify({
  kind: "compartmental",
  compound: "amlodipine",
  population: "adult",
  dose_mg: 10,
  interval_h: null,
  doses: 1,
  samples: 100,
});
const HEADERS = {
  "content-type": "application/json",
  "user-agent": "janus-load-smoke",
};

export const options = {
  vus: 3,
  duration: "30s",
  thresholds: {
    "http_req_duration{kind:read}": ["p(95)<500"],
    checks: ["rate>0.98"],
  },
};

export default function () {
  const read = { headers: HEADERS, tags: { kind: "read" } };
  check(http.get(`${BASE}/api/health`, read), {
    "health 200": (r) => r.status === 200,
  });
  check(http.get(`${BASE}/api/modelkit/drugs?limit=10`, read), {
    "model kit list 200": (r) => r.status === 200,
  });
  const queued = http.post(`${BASE}/api/simulate`, JOB, {
    headers: HEADERS,
    tags: { kind: "queue" },
  });
  check(queued, {
    "simulate accepted or limited": (r) => [200, 202, 429].includes(r.status),
  });
  if (queued.status === 200 || queued.status === 202) {
    const id = queued.json("job_id");
    if (id) {
      check(http.get(`${BASE}/api/simulate/jobs/${id}`, read), {
        "job answer 200": (r) => r.status === 200,
      });
    }
  }
  sleep(2);
}
