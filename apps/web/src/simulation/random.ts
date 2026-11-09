/**
 * Python's `random.Random` in TypeScript (simulation-service design §5, DP-S3): the Mersenne
 * Twister MT19937 seeded like CPython (`init_by_array` over the 32-bit words of the seed),
 * `random()` with 53-bit resolution, `uniform` and `gauss` with CPython's Box-Muller and its
 * cached second value. The same seed gives the same draws as the Python model, so the explorer
 * in the browser reproduces the time machine's Monte Carlo (property S1, shared fixtures).
 */
const N = 624;
const M = 397;
const TWOPI = 2 * Math.PI;

export class PyRandom {
  private mt = new Uint32Array(N);
  private mti = N + 1;
  private gaussNext: number | null = null;

  constructor(seed: number) {
    if (!Number.isSafeInteger(seed))
      throw new Error("seed must be a safe integer");
    let s = Math.abs(seed);
    const key: number[] = [];
    while (s > 0) {
      key.push(s % 0x100000000);
      s = Math.floor(s / 0x100000000);
    }
    this.initByArray(key.length ? key : [0]);
  }

  private initGenrand(s: number): void {
    const mt = this.mt;
    mt[0] = s >>> 0;
    for (let i = 1; i < N; i++) {
      const prev = mt[i - 1]! ^ (mt[i - 1]! >>> 30);
      mt[i] = (Math.imul(1812433253, prev) + i) >>> 0;
    }
    this.mti = N;
  }

  private initByArray(key: number[]): void {
    this.initGenrand(19650218);
    const mt = this.mt;
    let i = 1;
    let j = 0;
    for (let k = Math.max(N, key.length); k > 0; k--) {
      const prev = mt[i - 1]! ^ (mt[i - 1]! >>> 30);
      mt[i] = ((mt[i]! ^ Math.imul(prev, 1664525)) + key[j]! + j) >>> 0;
      i++;
      j++;
      if (i >= N) {
        mt[0] = mt[N - 1]!;
        i = 1;
      }
      if (j >= key.length) j = 0;
    }
    for (let k = N - 1; k > 0; k--) {
      const prev = mt[i - 1]! ^ (mt[i - 1]! >>> 30);
      mt[i] = ((mt[i]! ^ Math.imul(prev, 1566083941)) - i) >>> 0;
      i++;
      if (i >= N) {
        mt[0] = mt[N - 1]!;
        i = 1;
      }
    }
    mt[0] = 0x80000000;
  }

  private genrand(): number {
    const mt = this.mt;
    if (this.mti >= N) {
      let kk = 0;
      for (; kk < N - M; kk++) {
        const y = (mt[kk]! & 0x80000000) | (mt[kk + 1]! & 0x7fffffff);
        mt[kk] = mt[kk + M]! ^ (y >>> 1) ^ (y & 1 ? 0x9908b0df : 0);
      }
      for (; kk < N - 1; kk++) {
        const y = (mt[kk]! & 0x80000000) | (mt[kk + 1]! & 0x7fffffff);
        mt[kk] = mt[kk + (M - N)]! ^ (y >>> 1) ^ (y & 1 ? 0x9908b0df : 0);
      }
      const y = (mt[N - 1]! & 0x80000000) | (mt[0]! & 0x7fffffff);
      mt[N - 1] = mt[M - 1]! ^ (y >>> 1) ^ (y & 1 ? 0x9908b0df : 0);
      this.mti = 0;
    }
    let y = mt[this.mti++]!;
    y ^= y >>> 11;
    y ^= (y << 7) & 0x9d2c5680;
    y ^= (y << 15) & 0xefc60000;
    y ^= y >>> 18;
    return y >>> 0;
  }

  /** A float in [0, 1) with 53 random bits, as CPython's `random()`. */
  random(): number {
    const a = this.genrand() >>> 5;
    const b = this.genrand() >>> 6;
    return (a * 67108864 + b) / 9007199254740992;
  }

  uniform(a: number, b: number): number {
    return a + (b - a) * this.random();
  }

  /** CPython 3.12 `gauss`: Box-Muller, the second value kept for the next call. */
  gauss(mu = 0, sigma = 1): number {
    let z = this.gaussNext;
    this.gaussNext = null;
    if (z === null) {
      const x2pi = this.random() * TWOPI;
      const g2rad = Math.sqrt(-2 * Math.log(1 - this.random()));
      z = Math.cos(x2pi) * g2rad;
      this.gaussNext = Math.sin(x2pi) * g2rad;
    }
    return mu + z * sigma;
  }
}
