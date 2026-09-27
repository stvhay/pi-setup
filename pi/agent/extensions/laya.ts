import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type, type Static, type TSchema } from "typebox";
import { Check } from "typebox/value";

const ENDPOINT = "http://127.0.0.1:8001/v1/systemone";
const text = (maxLength: number) => Type.String({ minLength: 1, maxLength, pattern: "\\S" });
const closed = { additionalProperties: false };
const instructions = text(300);
const question = Type.Union([
  Type.Object({
    type: Type.Literal("choice"), instructions,
    criteria: Type.Record(Type.String({ pattern: "^[a-zA-Z0-9_-]{1,40}$" }), text(200), {
      minProperties: 2, maxProperties: 10, additionalProperties: false,
    }),
  }, closed),
  Type.Object({
    type: Type.Literal("score"), instructions,
    criteria: Type.Array(text(200), { minItems: 2, maxItems: 10, uniqueItems: true }),
  }, closed),
  Type.Object({
    type: Type.Literal("noul"), instructions,
    criteria: Type.Optional(Type.Object({ true: text(200), false: text(200) }, closed)),
  }, closed),
]);
const parameters = Type.Object({
  state: text(4000),
  questions: Type.Record(Type.String({ pattern: "^[a-zA-Z0-9_-]{1,40}$" }), question, {
    minProperties: 1, maxProperties: 8, additionalProperties: false,
  }),
}, closed);
const probability = Type.Number({ minimum: 0, maximum: 1 });
class LayaError extends Error {}

function answerSchema(q: Static<typeof question>): TSchema {
  const fields = {
    type: Type.Literal(q.type),
    confidence: probability,
    answer_confidence: Type.Optional(probability),
    action: Type.Optional(Type.Object({ act_probability: probability }, closed)),
  };
  if (q.type === "noul") return Type.Object({ ...fields, noul: probability }, closed);
  const keys = q.type === "choice" ? Object.keys(q.criteria) : q.criteria.map((_, i) => String(i));
  const probabilities = Type.Object(Object.fromEntries(keys.map(key => [key, probability])), closed);
  return q.type === "choice"
    ? Type.Object({ ...fields, probabilities, choice: Type.Union(keys.map(key => Type.Literal(key))) }, closed)
    : Type.Object({
      ...fields, probabilities, score: Type.Number({ minimum: 0, maximum: keys.length - 1 }),
      legend: Type.Object(Object.fromEntries(q.criteria.map((level, i) => [String(i), Type.Literal(level)])), closed),
    }, closed);
}

function validateAnswers(value: unknown, questions: Static<typeof parameters>["questions"]) {
  const schema = Type.Object(Object.fromEntries(Object.entries(questions).map(([id, q]) => [id, answerSchema(q)])), closed);
  if (!Check(schema, value)) throw new LayaError("Invalid Laya response: answer schema mismatch");
  // Rounded probabilities need tolerance; never renormalize or silently change answers.
  for (const answer of Object.values(value) as Array<{
    type: string; probabilities?: Record<string, number>; choice?: string; score?: number;
  }>) {
    if (!answer.probabilities) continue;
    const probabilities = answer.probabilities;
    const values = Object.values(probabilities);
    if (Math.abs(values.reduce((a, b) => a + b, 0) - 1) > 0.002 ||
        (answer.type === "choice" && probabilities[answer.choice!] !== Math.max(...values)) ||
        (answer.type === "score" && Math.abs(values.reduce((sum, p, i) => sum + p * i, 0) - answer.score!) > 0.003)) {
      throw new LayaError("Invalid Laya response: inconsistent probabilities");
    }
  }
  return value;
}

export default function laya(pi: ExtensionAPI): void {
  pi.registerTool({
    name: "laya_predict",
    label: "Laya Predict",
    description: "Ask local English Laya typed questions about short text. Returns advisory probabilities, not generated text. Requires an already-running server at 127.0.0.1:8001. No startup, downloads, retries, or cloud fallback. Keep text short: English checkpoint has a 512-token total context and may truncate. Never use confidence as permission or a security guarantee.",
    parameters,
    async execute(_id, params, signal) {
      if (!Check(parameters, params)) throw new LayaError("Invalid Laya input: check text and typed question limits");
      const body = JSON.stringify({ ...params, model: "english" });
      if (Buffer.byteLength(body) > 32768) throw new LayaError("Invalid Laya input: request exceeds 32768 bytes");
      const deadline = AbortSignal.timeout(30000);
      const combined = signal ? AbortSignal.any([signal, deadline]) : deadline;
      let reader: ReadableStreamDefaultReader<Uint8Array> | undefined;
      try {
        combined.throwIfAborted();
        const response = await fetch(ENDPOINT, {
          method: "POST", headers: { "Content-Type": "application/json" }, body,
          redirect: "error", signal: combined,
        });
        reader = response.body?.getReader();
        if (!response.ok) throw new LayaError(`Laya HTTP ${response.status}`);
        if (!reader) throw new LayaError("Invalid Laya response: empty body");
        const chunks: Uint8Array[] = [];
        let size = 0;
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          size += value.byteLength;
          if (size > 65536) throw new LayaError("Laya response exceeds 65536 bytes");
          chunks.push(value);
        }
        combined.throwIfAborted();
        let parsed: unknown;
        try { parsed = JSON.parse(Buffer.concat(chunks).toString("utf8")); }
        catch { throw new LayaError("Invalid Laya response: expected JSON"); }
        const answers = validateAnswers(
          parsed && typeof parsed === "object" && "answers" in parsed ? parsed.answers : undefined,
          params.questions,
        );
        const details = { answers };
        return { content: [{ type: "text", text: JSON.stringify(details) }], details };
      } catch (error) {
        if (signal?.aborted) throw new LayaError("Laya request cancelled");
        if (deadline.aborted) throw new LayaError("Laya request timed out after 30 seconds");
        if (error instanceof LayaError) throw error;
        throw new LayaError("Laya request failed at 127.0.0.1:8001; check the local server. No fallback attempted.");
      } finally {
        await reader?.cancel().catch(() => {});
        reader?.releaseLock();
      }
    },
  });
}
