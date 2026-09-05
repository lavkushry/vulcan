export type RequestContext = { requestId: string; principalId: string };
export type GenerationStatus = "queued" | "streaming" | "ready" | "accepted" | "rejected" | "failed";
export type ApiError = { error: { code: string; message: string; requestId: string; retryable: boolean } };
