import { z } from "zod";
import { createHash } from "node:crypto";

const element = z.object({ id: z.string().min(1), kind: z.enum(["text", "shape", "sticky", "connector", "freehand"]), x: z.number().finite().optional(), y: z.number().finite().optional(), width: z.number().finite().optional(), height: z.number().finite().optional() }).passthrough();
const proposalSchema = z.object({ elements: z.array(element).max(1000) });
export class GenerationValidationError extends Error { constructor() { super("AI proposal failed schema validation"); } }
export type GenerationResult = { status: "preview" | "accepted"; proposal: z.infer<typeof proposalSchema> };
type Model = (context: string, prompt: string, repair: boolean) => Promise<unknown>;
type Commit = (proposal: z.infer<typeof proposalSchema>, generationId: string) => Promise<void>;

export function sanitizeContext(context: string): string {
  return context.split(/\r?\n/).filter((line) => !/^\s*(?:ignore\s+previous|system\s*:|assistant\s*:)/i.test(line)).join("\n").replace(/(?:sk-[A-Za-z0-9_-]{8,}|Bearer\s+[A-Za-z0-9._-]{8,}|-----BEGIN[^-]+-----[\s\S]*?-----END[^-]+-----)/gi, "[REDACTED]");
}

export class AiGenerationService {
  private readonly results = new Map<string, GenerationResult>();
  private readonly inputs = new Map<string, string>();
  private readonly accepted = new Set<string>();
  constructor(private readonly model: Model, private readonly commit: Commit = async () => {}) {}

  async generate(generationId: string, context: string, prompt: string): Promise<GenerationResult> {
    const prior = this.results.get(generationId);
    const boundedContext = sanitizeContext(context).slice(0, 8_192 * 4);
    const fingerprint = createHash("sha256").update(JSON.stringify({ context: boundedContext, prompt })).digest("hex");
    if (prior) {
      if (this.inputs.get(generationId) !== fingerprint) throw new Error("generation idempotency key reused with different input");
      return prior;
    }
    let raw: unknown;
    let repair = false;
    for (let attempt = 0; attempt < 3; attempt += 1) {
      try { raw = await this.model(boundedContext, prompt, repair); break; }
      catch (error) {
        if ((error as { status?: number }).status !== 429 || attempt === 2) throw error;
        await new Promise((resolve) => setTimeout(resolve, 10 * (attempt + 1)));
      }
    }
    let parsed = proposalSchema.safeParse(raw);
    if (!parsed.success && !repair) {
      repair = true;
      parsed = proposalSchema.safeParse(await this.model(boundedContext, prompt, repair));
    }
    if (!parsed.success) throw new GenerationValidationError();
    const result: GenerationResult = { status: "preview", proposal: parsed.data };
    this.inputs.set(generationId, fingerprint);
    this.results.set(generationId, result);
    return result;
  }

  async accept(generationId: string): Promise<GenerationResult> {
    const result = this.results.get(generationId);
    if (!result) throw new Error("generation not found");
    if (this.accepted.has(generationId)) throw new Error("generation already accepted");
    await this.commit(result.proposal, generationId);
    this.accepted.add(generationId);
    const accepted = { ...result, status: "accepted" as const };
    this.results.set(generationId, accepted);
    return accepted;
  }

  get(generationId: string): GenerationResult | undefined { return this.results.get(generationId); }
}
