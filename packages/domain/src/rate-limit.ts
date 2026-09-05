export type Clock = () => number;
type Bucket = { startedAt: number; count: number };

export class FixedWindowLimiter {
  private readonly buckets = new Map<string, Bucket>();
  constructor(private readonly clock: Clock = () => Date.now()) {}
  allow(key: string, limit: number, windowMs: number): boolean {
    if (limit < 1 || windowMs < 1) throw new RangeError("rate limit must be positive");
    const now = this.clock();
    const prior = this.buckets.get(key);
    const bucket = !prior || now - prior.startedAt >= windowMs ? { startedAt: now, count: 0 } : prior;
    if (bucket.count >= limit) return false;
    bucket.count += 1;
    this.buckets.set(key, bucket);
    return true;
  }
}
