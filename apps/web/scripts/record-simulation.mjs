// Records the queued simulation service end to end for demo mode and the tests
// (simulation-service design §2): the allow-list answer and one finished job for the default inputs
// of each model (the form's defaults), run by the real simulator worker. The API must run with
// JANUS_SIMULATION=on, a database with migration 0014 and the worker. Virtual populations only;
// no personal data.
//   JANUS_API=http://127.0.0.1:8013 node scripts/record-simulation.mjs
import { writeFileSync } from "node:fs";
import { join } from "node:path";

const api = (process.env.JANUS_API ?? "http://127.0.0.1:8000").replace(
  /\/$/,
  "",
);
async function call(path, body) {
  const res = await fetch(`${api}${path}`, {
    method: body ? "POST" : "GET",
    headers: body ? { "content-type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
    signal: AbortSignal.timeout(60_000),
  });
  if (!res.ok) throw new Error(`${path}: HTTP ${res.status}`);
  return res.json();
}

const compounds = await call("/simulate/compounds");
const c = compounds.compartmental[0];
const requests = [
  {
    kind: "compartmental",
    compound: c.id,
    population: c.populations[0].id,
    dose_mg: c.dose_mg.default,
    interval_h: null,
    doses: 1,
    samples: 1000,
  },
  {
    kind: "httk_population",
    compound: compounds.httk.at(-1).id,
    samples: 1000,
  },
];
const jobs = [];
for (const request of requests) {
  let job = await call("/simulate", request);
  for (let i = 0; i < 120 && ["queued", "running"].includes(job.state); i++) {
    await new Promise((r) => setTimeout(r, 1000));
    job = await call(`/simulate/jobs/${job.job_id}`);
  }
  if (job.state !== "done") throw new Error(`${request.kind}: ${job.state}`);
  jobs.push({ request, job: { ...job, cached: false } });
}
writeFileSync(
  join(import.meta.dirname, "../src/simulation/simulate.recorded.json"),
  JSON.stringify(
    { recorded: new Date().toISOString().slice(0, 10), compounds, jobs },
    null,
    1,
  ) + "\n",
);
console.log(`recorded ${jobs.length} jobs`);
