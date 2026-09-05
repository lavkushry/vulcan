export type CorrelationContext = { requestId: string; boardId?: string; operationId?: string; generationId?: string };
export type Span = { name: string; attributes: CorrelationContext; data?: Record<string, unknown> };

export interface Tracer { record(name: string, context: CorrelationContext, data?: Record<string, unknown>): void; }

export class InMemoryTracer implements Tracer {
  readonly spans: Span[] = [];
  record(name: string, context: CorrelationContext, data?: Record<string, unknown>): void {
    if (!context.requestId) throw new Error("requestId is required");
    this.spans.push({ name, attributes: { ...context }, data });
  }
}

export type FetchLike = (input: string, init?: RequestInit) => Promise<unknown>;

/** Minimal OTLP/HTTP exporter; callers can inject fetch for tests or runtimes without global fetch. */
export class OtlpHttpTracer implements Tracer {
  private readonly fetcher: FetchLike;
  constructor(private readonly endpoint: string, fetcher?: FetchLike) {
    this.fetcher = fetcher ?? ((input, init) => fetch(input, init));
  }
  record(name: string, context: CorrelationContext, data?: Record<string, unknown>): void {
    if (!context.requestId) throw new Error("requestId is required");
    const correlation = { request_id: context.requestId, board_id: context.boardId, operation_id: context.operationId, generation_id: context.generationId };
    const attributes = Object.entries({ ...correlation, ...data }).filter(([, value]) => value !== undefined).map(([key, value]) => ({ key, value: { stringValue: String(value) } }));
    const payload = { resourceSpans: [{ scopeSpans: [{ spans: [{ name, attributes }] }] }] };
    void this.fetcher(this.endpoint, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(payload) }).catch(() => undefined);
  }
}
