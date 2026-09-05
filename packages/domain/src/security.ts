import { createHash, randomBytes } from "node:crypto";

export type ShareScope = "view" | "edit";
export const hashShareSecret = (value: string) => createHash("sha256").update(value).digest("hex");

export function randomShareSecret(): string { return randomBytes(32).toString("base64url"); }

export class ShareLink {
  private revoked = false;
  private constructor(readonly boardId: string, readonly scope: ShareScope, readonly expiresAt: number, readonly tokenHash: string) {}
  static issue(boardId: string, scope: ShareScope, ttlSeconds: number, secret: string, now = Date.now()): ShareLink {
    if (scope !== "view" && scope !== "edit") throw new RangeError("share link scope must be view or edit");
    if (ttlSeconds <= 0 || ttlSeconds > 24 * 60 * 60) throw new RangeError("share link TTL must be between 1 second and 24 hours");
    return new ShareLink(boardId, scope, now + ttlSeconds * 1000, hashShareSecret(secret));
  }
  verify(secret: string, boardId: string, requiredScope: ShareScope, now: number): boolean {
    const scopeOk = requiredScope === "view" || this.scope === "edit";
    return !this.revoked && this.boardId === boardId && scopeOk && now < this.expiresAt && hashShareSecret(secret) === this.tokenHash;
  }
  revoke(): void { this.revoked = true; }
}
