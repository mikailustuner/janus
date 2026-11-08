/**
 * Safe browser storage (experience design §4, DP5, Req 9.2–9.5, P16).
 *
 * Every getItem / setItem / removeItem is wrapped. On the first failure (blocked, full, throwing
 * storage) the store switches to an in-memory map for the rest of the session and raises the
 * `unavailable` notice once. Documents carry a schema version and are validated on read; a
 * document of unknown shape is not used, raises the `invalid` notice, and is never sent anywhere.
 */

export interface StorageLike {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
  readonly length: number;
  key(index: number): string | null;
}

export const PREFIX = "janus.v1.";

export type Notice = "unavailable" | "invalid";

export type ReadResult<T> =
  { status: "ok"; value: T } | { status: "absent" } | { status: "invalid" };

export class SafeStorage {
  private memory = new Map<string, string>();
  private inMemory = false;
  private notices = new Set<Notice>();
  private listeners = new Set<() => void>();

  constructor(private readonly backend: () => StorageLike | null) {}

  /** True once storage failed and data is kept for this session only. */
  get memoryOnly(): boolean {
    return this.inMemory;
  }

  /** The notices raised so far (each at most once per session). */
  get raised(): ReadonlySet<Notice> {
    return this.notices;
  }

  onNotice(listener: () => void): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  private raise(n: Notice) {
    if (this.notices.has(n)) return;
    this.notices.add(n);
    for (const l of this.listeners) l();
  }

  private fallBack() {
    if (!this.inMemory) {
      this.inMemory = true;
      this.raise("unavailable");
    }
  }

  private store(): StorageLike | null {
    if (this.inMemory) return null;
    try {
      const s = this.backend();
      if (!s) this.fallBack();
      return s;
    } catch {
      this.fallBack();
      return null;
    }
  }

  getRaw(key: string): string | null {
    const s = this.store();
    if (s) {
      try {
        return s.getItem(key);
      } catch {
        this.fallBack();
      }
    }
    return this.memory.get(key) ?? null;
  }

  setRaw(key: string, value: string): void {
    this.memory.set(key, value);
    const s = this.store();
    if (!s) return;
    try {
      s.setItem(key, value);
    } catch {
      this.fallBack();
    }
  }

  remove(key: string): void {
    this.memory.delete(key);
    const s = this.store();
    if (!s) return;
    try {
      s.removeItem(key);
    } catch {
      this.fallBack();
    }
  }

  /** Reads and validates a JSON document. Never throws. */
  read<T>(key: string, validate: (v: unknown) => T | null): ReadResult<T> {
    const raw = this.getRaw(key);
    if (raw === null) return { status: "absent" };
    let parsed: unknown;
    try {
      parsed = JSON.parse(raw);
    } catch {
      this.raise("invalid");
      return { status: "invalid" };
    }
    let value: T | null = null;
    try {
      value = validate(parsed);
    } catch {
      value = null;
    }
    if (value === null) {
      this.raise("invalid");
      return { status: "invalid" };
    }
    return { status: "ok", value };
  }

  write(key: string, value: unknown): void {
    let raw: string;
    try {
      raw = JSON.stringify(value);
    } catch {
      return;
    }
    this.setRaw(key, raw);
  }

  /** Every Janus key, from the backend when available and from the session map. */
  keys(): string[] {
    const out = new Set<string>(
      [...this.memory.keys()].filter((k) => k.startsWith("janus.")),
    );
    const s = this.store();
    if (s) {
      try {
        for (let i = 0; i < s.length; i++) {
          const k = s.key(i);
          if (k?.startsWith("janus.")) out.add(k);
        }
      } catch {
        this.fallBack();
      }
    }
    return [...out];
  }
}

const browserLocal = (): StorageLike | null =>
  typeof window === "undefined" ? null : window.localStorage;

/** The app's storage. On the server it has no backend and is never written. */
export const storage = new SafeStorage(browserLocal);

/** A versioned document with subscribe / getSnapshot for useSyncExternalStore (§4.1). */
export class Doc<T> {
  private cache: T | undefined;
  private listeners = new Set<() => void>();

  constructor(
    private readonly store: SafeStorage,
    readonly key: string,
    private readonly validate: (v: unknown) => T | null,
    private readonly initial: () => T,
  ) {}

  get(): T {
    if (this.cache === undefined) {
      const r = this.store.read(this.key, this.validate);
      this.cache = r.status === "ok" ? r.value : this.initial();
    }
    return this.cache;
  }

  set(next: T): void {
    this.cache = next;
    this.store.write(this.key, next);
    for (const l of this.listeners) l();
  }

  update(f: (current: T) => T): void {
    this.set(f(this.get()));
  }

  /** Forget the cached value (after "delete everything"). */
  reset(): void {
    this.cache = undefined;
    for (const l of this.listeners) l();
  }

  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  getSnapshot = (): T => this.get();
}
