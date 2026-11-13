/**
 * fast-check settings for the property tests (experience design §17).
 * `FC_PROFILE=ci` runs 300 cases per property with a fixed seed, `nightly` 1000 with a random one,
 * the default `dev` profile 100 with a random one. The seed is printed by fast-check on failure;
 * set `FC_SEED` to replay it.
 */
import fc from "fast-check";

const profile = process.env.FC_PROFILE ?? "dev";
const runs = profile === "nightly" ? 1000 : profile === "ci" ? 300 : 100;
// CI replays the same cases on every run (a red build is reproducible); `dev` and `nightly` draw a
// new seed each time, and nightly counterexamples are pinned with `examples` (docs/testing.md).
const CI_SEED = 20261113;
const seed = process.env.FC_SEED
  ? Number(process.env.FC_SEED)
  : profile === "ci"
    ? CI_SEED
    : undefined;

export const fcParams: fc.Parameters<unknown> = {
  numRuns: runs,
  ...(seed === undefined ? {} : { seed }),
};

/** `fc.assert` with the profile's settings. */
export function check<Ts extends [unknown, ...unknown[]]>(
  property: fc.IProperty<Ts> | fc.IAsyncProperty<Ts>,
  params: fc.Parameters<Ts> = {},
) {
  return fc.assert(property as fc.IProperty<Ts>, {
    ...(fcParams as fc.Parameters<Ts>),
    ...params,
  });
}

export { fc };
