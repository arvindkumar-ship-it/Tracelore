import type { Trace } from "@/lib/schemas";
export interface PositionedSpan {
  index: number;
  row: number;
  start: number;
  end: number;
  depth: number;
}

class Lanes {
  private size = 1;
  private tree: Float64Array;
  constructor(count: number) {
    while (this.size < count) this.size *= 2;
    this.tree = new Float64Array(this.size * 2).fill(-Infinity);
  }
  reserve(row: number, end: number): void {
    let index = this.size + row;
    this.tree[index] = end;
    while (index > 1) {
      index = Math.floor(index / 2);
      this.tree[index] = Math.min(
        this.tree[index * 2],
        this.tree[index * 2 + 1],
      );
    }
  }
  first(
    minimum: number,
    start: number,
    node = 1,
    left = 0,
    right = this.size,
  ): number {
    if (right <= minimum || this.tree[node] > start) return -1;
    if (right - left === 1) return left;
    const middle = (left + right) / 2;
    const first = this.first(minimum, start, node * 2, left, middle);
    return first >= 0
      ? first
      : this.first(minimum, start, node * 2 + 1, middle, right);
  }
}
export function layout(trace: Trace): PositionedSpan[] {
  const spans = trace.spans,
    indices = new Map(spans.id.map((id, index) => [id, index]));
  const children = new Map<number, number[]>(),
    roots: number[] = [];
  spans.id.forEach((_, index) => {
    const parent =
      spans.parent[index] === null
        ? undefined
        : indices.get(spans.parent[index]!);
    if (parent === undefined || parent === index) roots.push(index);
    else children.set(parent, [...(children.get(parent) ?? []), index]);
  });
  const compare = (a: number, b: number) =>
    spans.start_us[a] - spans.start_us[b] || a - b;
  const pending = roots
    .sort(compare)
    .reverse()
    .map((index) => ({ index, minimum: 0, depth: 0 }));
  const visited = new Set<number>(),
    lanes = new Lanes(spans.id.length + 1),
    positioned: PositionedSpan[] = [];
  while (pending.length) {
    const { index, minimum, depth } = pending.pop()!;
    if (visited.has(index)) continue;
    visited.add(index);
    const start = spans.start_us[index],
      end = start + spans.dur_us[index];
    const row = lanes.first(minimum, start);
    lanes.reserve(row, end);
    positioned.push({ index, row, start, end, depth });
    for (const child of [...(children.get(index) ?? [])]
      .sort(compare)
      .reverse())
      pending.push({ index: child, minimum: row + 1, depth: depth + 1 });
  }
  for (let index = 0; index < spans.id.length; index++)
    if (!visited.has(index))
      positioned.push({
        index,
        row: positioned.length,
        start: spans.start_us[index],
        end: spans.start_us[index] + spans.dur_us[index],
        depth: 0,
      });
  return positioned;
}
