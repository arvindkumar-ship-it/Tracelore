"use client";
export function ScrubBar({
  count,
  index,
  onChange,
}: {
  count: number;
  index: number;
  onChange: (index: number) => void;
}) {
  return (
    <div className="scrubber">
      <label className="subtle" htmlFor="scrubber">
        Event cursor{" "}
        <span className="mono">
          {index + 1} / {count}
        </span>{" "}
        <span className="cursor-hint"> · Use ← → to step</span>
      </label>
      <input
        id="scrubber"
        className="scrub"
        type="range"
        min={0}
        max={Math.max(0, count - 1)}
        value={index}
        onChange={(event) => onChange(Number(event.target.value))}
        aria-label="Event cursor"
      />
    </div>
  );
}
