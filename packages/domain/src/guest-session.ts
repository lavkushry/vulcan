import { hashShareSecret, randomShareSecret, ShareLink, ShareScope } from "./security.js";

type Clock = () => number;
type Session = { link: ShareLink; quota: number; writes: number; revokedAt?: number };

export class GuestSessionRegistry {
  private readonly sessions = new Map<string, Session>();
  constructor(private readonly clock: Clock = () => Date.now(), private readonly revocationCacheMs = 60_000) {}
  issue(boardId: string, scope: ShareScope, ttlSeconds: number, writeQuota: number): string {
    if (writeQuota < 0) throw new RangeError("write quota must be non-negative");
    const secret = randomShareSecret();
    const link = ShareLink.issue(boardId, scope, ttlSeconds, secret, this.clock());
    this.sessions.set(link.tokenHash, { link, quota: writeQuota, writes: 0 });
    return secret;
  }
  authorize(secret: string, boardId: string, scope: ShareScope): boolean {
    const session = this.sessions.get(hashShareSecret(secret));
    if (!session) return false;
    if (session.revokedAt !== undefined && this.clock() - session.revokedAt <= this.revocationCacheMs) return false;
    return session.link.verify(secret, boardId, scope, this.clock());
  }
  consumeWrite(secret: string): boolean {
    const session = this.sessions.get(hashShareSecret(secret));
    if (!session || !session.link.verify(secret, session.link.boardId, "edit", this.clock())) return false;
    if (session.writes >= session.quota) return false;
    session.writes += 1;
    return true;
  }
  revoke(secret: string): void {
    const session = this.sessions.get(hashShareSecret(secret));
    if (!session) return;
    session.link.revoke();
    session.revokedAt = this.clock();
  }
}
