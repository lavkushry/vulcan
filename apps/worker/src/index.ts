import { AiGenerationService, type GenerationResult } from "@vulcan/domain";

export const serviceName = "vulcan-worker";
type Job = { generationId: string; context: string; prompt: string };
type Model = (context: string, prompt: string, repair: boolean) => Promise<unknown>;
type RedisGenerationClient = {
  set(key: string, value: string, options: { NX: true }): Promise<"OK" | null>;
  xAdd(key: string, id: string, fields: Record<string, string>): Promise<string>;
  hSet(key: string, fields: Record<string, string>): Promise<unknown>;
  del(key: string): Promise<number>;
  xRead?(streams: Array<{ key: string; id: string }>, options?: { COUNT?: number; BLOCK?: number }): Promise<Array<{ messages: Array<{ id: string; message: Record<string, string> }> }> | null>;
  xAck?(key: string, group: string, id: string): Promise<number>;
};

export class GenerationQueue {
  private readonly jobs = new Map<string, Promise<GenerationResult>>();
  private readonly service: AiGenerationService;
  constructor(model: Model) { this.service = new AiGenerationService(model); }
  enqueue(job: Job): Promise<GenerationResult> {
    const prior = this.jobs.get(job.generationId);
    if (prior) return prior;
    const result = this.service.generate(job.generationId, job.context, job.prompt);
    this.jobs.set(job.generationId, result);
    return result;
  }
}

export class RedisGenerationJobTransport {
  constructor(private readonly client: RedisGenerationClient, private readonly streamKey = "vulcan:generation:jobs") {}
  async enqueue(job: Job): Promise<{ status: "queued"; id: string; duplicate: boolean }> {
    const dedupeKey = `vulcan:generation:${job.generationId}`;
    const claimed = await this.client.set(dedupeKey, "queued", { NX: true });
    if (claimed !== "OK") return { status: "queued", id: dedupeKey, duplicate: true };
    let id: string;
    try {
      id = await this.client.xAdd(this.streamKey, "*", { data: JSON.stringify(job) });
    } catch (error) {
      await this.client.del(dedupeKey);
      throw error;
    }
    await this.client.hSet(dedupeKey, { status: "queued", streamId: id });
    return { status: "queued", id, duplicate: false };
  }
}

export class RedisGenerationWorker {
  constructor(private readonly client: RedisGenerationClient, private readonly queue: GenerationQueue, private readonly streamKey = "vulcan:generation:jobs", private readonly group = "vulcan-workers", private readonly maxAttempts = 3) {}

  async processOnce(): Promise<number> {
    if (!this.client.xRead) return 0;
    const result = await this.client.xRead([{ key: this.streamKey, id: ">" }], { COUNT: 10, BLOCK: 1 });
    const messages = result?.flatMap((stream) => stream.messages) ?? [];
    for (const message of messages) {
      let job: Job | undefined;
      try { job = JSON.parse(message.message.data) as Job; if (!job?.generationId || !job.context || !job.prompt) throw new Error("invalid job"); }
      catch { await this.client.hSet(`vulcan:generation:invalid:${message.id}`, { status: "failed", error: "invalid job" }); if (this.client.xAck) await this.client.xAck(this.streamKey, this.group, message.id); continue; }
      const stateKey = `vulcan:generation:${job.generationId}`;
      try {
        await this.client.hSet(stateKey, { status: "streaming" });
        await this.queue.enqueue(job);
        await this.client.hSet(stateKey, { status: "ready", attempts: "1" });
        if (this.client.xAck) await this.client.xAck(this.streamKey, this.group, message.id);
      } catch (error) {
        const attempts = Number(message.message.attempts || "0") + 1;
        await this.client.hSet(stateKey, { status: attempts >= this.maxAttempts ? "failed" : "queued", attempts: String(attempts), error: String(error) });
        if (attempts >= this.maxAttempts && this.client.xAck) await this.client.xAck(this.streamKey, this.group, message.id);
      }
    }
    return messages.length;
  }
}
