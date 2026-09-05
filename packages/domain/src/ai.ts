export type ProposedElement = { id: string; kind: "text" | "shape" | "sticky" | "connector" | "freehand"; [key: string]: unknown };
export type Proposal = { elements: ProposedElement[] };
const kinds = new Set(["text", "shape", "sticky", "connector", "freehand"]);

export function validateProposal(input: unknown): Proposal {
  if (!input || typeof input !== "object" || !Array.isArray((input as { elements?: unknown }).elements)) throw new Error("proposal.elements is required");
  const elements = (input as { elements: unknown[] }).elements;
  if (elements.length > 1000) throw new Error("proposal elements maximum is 1000");
  for (const element of elements) {
    if (!element || typeof element !== "object") throw new Error("element must be an object");
    const candidate = element as Record<string, unknown>;
    if (typeof candidate.id !== "string" || !kinds.has(String(candidate.kind))) throw new Error("element id and kind are required");
    for (const key of ["x", "y", "width", "height"]) if (key in candidate && (typeof candidate[key] !== "number" || !Number.isFinite(candidate[key] as number))) throw new Error("geometry must be numeric");
  }
  return { elements: elements as ProposedElement[] };
}
