import type { PositionedSpan } from "./layout";
export interface SpatialGrid {
  origin: number;
  binWidth: number;
  buckets: Map<string, PositionedSpan[]>;
}
export function buildGrid(
  spans: PositionedSpan[],
  origin: number,
  range: number,
): SpatialGrid {
  const binWidth = Math.max(1, Math.ceil(range / 256)),
    buckets = new Map<string, PositionedSpan[]>();
  for (const span of spans) {
    const first = Math.floor((span.start - origin) / binWidth),
      last = Math.floor((span.end - origin) / binWidth);
    for (let bin = first; bin <= last; bin++) {
      const key = `${span.row}:${bin}`,
        bucket = buckets.get(key) ?? [];
      bucket.push(span);
      buckets.set(key, bucket);
    }
  }
  for (const bucket of buckets.values())
    bucket.sort((a, b) => a.start - b.start);
  return { origin, binWidth, buckets };
}
export function hitTest(
  grid: SpatialGrid,
  row: number,
  time: number,
): PositionedSpan | undefined {
  const bucket = grid.buckets.get(
    `${row}:${Math.floor((time - grid.origin) / grid.binWidth)}`,
  );
  if (!bucket?.length) return undefined;
  let left = 0,
    right = bucket.length;
  while (left < right) {
    const middle = (left + right) >>> 1;
    if (bucket[middle].start <= time) left = middle + 1;
    else right = middle;
  }
  const span = bucket[left - 1];
  return span && time <= span.end ? span : undefined;
}
