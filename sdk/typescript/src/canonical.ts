import { createHash } from "node:crypto";

function numberText(value: number, forceFloat: boolean): string {
  if (!Number.isFinite(value)) throw new TypeError("non-finite JSON number");
  if (Object.is(value, -0)) return forceFloat ? "-0.0" : "0";
  const magnitude = Math.abs(value);
  let result =
    (magnitude > 0 && magnitude < 1e-4) || (forceFloat && magnitude >= 1e16)
      ? value.toExponential()
      : value.toString();
  result = result.replace(
    /e([+-]?)(\d+)$/,
    (_, sign: string, digits: string) =>
      `e${sign || "+"}${digits.padStart(2, "0")}`,
  );
  if (forceFloat && !result.includes(".") && !result.includes("e"))
    result += ".0";
  return result;
}

export function canonicalJson(value: unknown, field = ""): string {
  if (value === null) return "null";
  if (typeof value === "string" || typeof value === "boolean")
    return JSON.stringify(value);
  if (typeof value === "number")
    return numberText(value, field === "duration_ms");
  if (Array.isArray(value))
    return `[${value.map((item) => canonicalJson(item)).join(",")}]`;
  if (typeof value !== "object") throw new TypeError("value is not JSON");
  return `{${Object.keys(value)
    .sort(compareKeys)
    .map(
      (key) =>
        `${JSON.stringify(key)}:${canonicalJson(
          (value as Record<string, unknown>)[key],
          key,
        )}`,
    )
    .join(",")}}`;
}

export function sha256(data: string | Uint8Array): string {
  return createHash("sha256").update(data).digest("hex");
}

export function eventHash(event: Record<string, unknown>): string {
  const { event_hash: ignored, ...unsigned } = event;
  return sha256(canonicalJson(unsigned));
}

function compareKeys(first: string, second: string): number {
  const left = [...first],
    right = [...second];
  for (let index = 0; index < Math.min(left.length, right.length); index++) {
    const difference =
      left[index].codePointAt(0)! - right[index].codePointAt(0)!;
    if (difference) return difference;
  }
  return left.length - right.length;
}
