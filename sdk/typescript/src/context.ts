import { AsyncLocalStorage } from "node:async_hooks";

export const TRACE_HEADER = "x-tracelore-trace";
export const context = new AsyncLocalStorage<{
  traceId: string;
  spanId: string;
}>();
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function parseHeader(
  value: string | undefined,
): [string, string] | null {
  const parts = value?.split(":");
  return parts?.length === 2 && parts.every((part) => uuid.test(part))
    ? [parts[0].toLowerCase(), parts[1].toLowerCase()]
    : null;
}
