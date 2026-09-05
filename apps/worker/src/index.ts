import { AiGenerationService, type GenerationResult } from "@vulcan/domain";

export const serviceName = "vulcan-worker";
type Job = { generationId: string; context: string; prompt: string };
type Model = (context: string, prompt: string, repair: boolean) => Promise<unknown>;
type RedisGenerationClient = {
  set(key: string, value: string, options: { NX: true }): Promise<"OK" | null>;
  xAdd(key: string, id: string, fields: Record<string, string>): Promise<string>;
  hSet(key: string, fields: Record<string, string>): Promise<unknown>;
  del(key: string): Promise<number>;
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
