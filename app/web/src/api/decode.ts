// JSON is untrusted, even when it comes from our own API or browser storage.
export type Decoder<T> = (value: unknown) => T;
export function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("Expected an object.");
  return value as Record<string, unknown>;
}
export const text: Decoder<string> = (value) => {
  if (typeof value !== "string") throw new Error("Expected text.");
  return value;
};
export const number: Decoder<number> = (value) => {
  if (typeof value !== "number" || !Number.isFinite(value)) throw new Error("Expected a finite number.");
  return value;
};
export const boolean: Decoder<boolean> = (value) => {
  if (typeof value !== "boolean") throw new Error("Expected a boolean.");
  return value;
};
export function array<T>(decode: Decoder<T>): Decoder<T[]> {
  return (value) => {
    if (!Array.isArray(value)) throw new Error("Expected an array.");
    return value.map((item: unknown) => decode(item));
  };
}
export function dictionary<T>(decode: Decoder<T>): Decoder<Record<string, T>> {
  return (value) => Object.fromEntries(Object.entries(record(value)).map(([key, item]) => [key, decode(item)]));
}
// Optional API fields may be absent/null. Known fields must have the right shape;
// extra server fields are ignored rather than leaking unvalidated data into state.
export function shape<S extends Record<string, Decoder<unknown>>>(fields: S) {
  type Result = { [K in keyof S]?: ReturnType<S[K]> };
  return (value: unknown): Result => {
    const input = record(value);
    const output: Record<string, unknown> = {};
    for (const key of Object.keys(fields)) {
      if (input[key] !== undefined && input[key] !== null) output[key] = fields[key](input[key]);
    }
    // Each field was decoded by its corresponding schema above.
    return output as Result;
  };
}
export async function json<T>(response: Response, decode: Decoder<T>): Promise<T> {
  const value: unknown = await response.json();
  return decode(value);
}
export function errorInfo(value: unknown): { name?: string; message?: string; status?: number } {
  if (!value || typeof value !== "object") return {};
  return {
    name: "name" in value && typeof value.name === "string" ? value.name : undefined,
    message: "message" in value && typeof value.message === "string" ? value.message : undefined,
    status: "status" in value && typeof value.status === "number" ? value.status : undefined,
  };
}
