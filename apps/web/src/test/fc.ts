/**
 * fast-check settings for the property tests (experience design §17).
 * `FC_PROFILE=ci` runs 300 cases per property, the default `dev` profile 100. The seed is printed
 * by fast-check on failure; set `FC_SEED` to replay it.
 */
import fc from "fast-check";

const runs = process.env.FC_PROFILE === "ci" ? 300 : 100;
const seed = process.env.FC_SEED ? Number(process.env.FC_SEED) : undefined;

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
