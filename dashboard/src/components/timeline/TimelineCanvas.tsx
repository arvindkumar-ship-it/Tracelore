"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Trace } from "@/lib/schemas";
import { Icon } from "../Icon";
import { duration } from "@/lib/format";
import { layout } from "./layout";
import { buildGrid, hitTest } from "./hitTest";

const COLORS = [
  "#829579",
  "#78979e",
  "#9c8d9e",
  "#ba9a64",
  "#7e9a90",
  "#b58377",
];
const ROW_HEIGHT = 27,
  HEIGHT = 335,
  LABEL_WIDTH = 140;
export function TimelineCanvas({
  trace,
  selected,
  onSelect,
}: {
  trace: Trace;
  selected: string;
  onSelect: (id: string) => void;
}) {
  const canvas = useRef<HTMLCanvasElement>(null),
    container = useRef<HTMLDivElement>(null);
  const positioned = useMemo(() => layout(trace), [trace]);
  const minimum = Math.min(...trace.spans.start_us),
    maximum = Math.max(...positioned.map((span) => span.end));
  const total = Math.max(1, maximum - minimum);
  const [view, setView] = useState<[number, number]>([minimum, maximum]),
    [scroll, setScroll] = useState(0);
  const [hover, setHover] = useState<{
    index: number;
    x: number;
    y: number;
  } | null>(null);
  const [width, setWidth] = useState(800),
    [mobileScroll, setMobileScroll] = useState(0);
  const grid = useMemo(
    () => buildGrid(positioned, minimum, total),
    [positioned, minimum, total],
  );
  const rows = Math.max(...positioned.map((span) => span.row)) + 1;
  const draw = useCallback(() => {
    const element = canvas.current,
      context = element?.getContext("2d");
    if (!element || !context) return;
    const started = performance.now();
    const ratio = devicePixelRatio || 1;
    element.width = width * ratio;
    element.height = HEIGHT * ratio;
    context.scale(ratio, ratio);
    context.fillStyle = "#fcfbf8";
    context.fillRect(0, 0, width, HEIGHT);
    const plotWidth = width - LABEL_WIDTH - 15,
      range = Math.max(1, view[1] - view[0]);
    context.font =
      "11px Inter,-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif";
    for (let tick = 0; tick <= 5; tick++) {
      const x = LABEL_WIDTH + (plotWidth * tick) / 5;
      context.strokeStyle = "#eae7e0";
      context.beginPath();
      context.moveTo(x, 24);
      context.lineTo(x, HEIGHT);
      context.stroke();
      context.fillStyle = "#786f61";
      context.textAlign = tick === 5 ? "right" : "left";
      context.fillText(
        duration((view[0] - minimum + (range * tick) / 5) / 1000),
        tick === 5 ? x - 4 : x + 4,
        14,
      );
    }
    context.textAlign = "left";
    context.fillStyle = "#786f61";
    context.fillText("Service", 8, 14);
    for (const span of positioned) {
      const y = 30 + span.row * ROW_HEIGHT - scroll;
      if (y < 20 || y > HEIGHT || span.end < view[0] || span.start > view[1])
        continue;
      const index = span.index,
        x = LABEL_WIDTH + ((span.start - view[0]) / range) * plotWidth;
      const length = Math.max(3, ((span.end - span.start) / range) * plotWidth);
      context.save();
      context.beginPath();
      context.rect(LABEL_WIDTH, 25, plotWidth, HEIGHT);
      context.clip();
      context.fillStyle =
        COLORS[trace.spans.service_idx[index] % COLORS.length];
      context.globalAlpha = selected === trace.spans.event_id[index] ? 1 : 0.62;
      context.fillRect(x, y, length, 17);
      context.globalAlpha = 1;
      if (
        trace.spans.status[index] === "error" ||
        selected === trace.spans.event_id[index]
      ) {
        context.strokeStyle =
          trace.spans.status[index] === "error" ? "#b85849" : "#5c6653";
        context.lineWidth = 2;
        context.strokeRect(x, y, length, 17);
      }
      context.restore();
      context.fillStyle = "#625d53";
      context.fillText(
        trace.dict.services[trace.spans.service_idx[index]].slice(0, 16),
        8,
        y + 12,
      );
    }
    element.dataset.drawMs = (performance.now() - started).toFixed(3);
  }, [width, view, minimum, positioned, scroll, selected, trace]);
  useEffect(() => {
    const frame = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(frame);
  }, [draw]);
  useEffect(() => {
    if (!container.current) return;
    const observer = new ResizeObserver((entries) =>
      setWidth(entries[0].contentRect.width),
    );
    observer.observe(container.current);
    return () => observer.disconnect();
  }, []);
  const locate = (event: React.MouseEvent<HTMLCanvasElement>) => {
    const bounds = event.currentTarget.getBoundingClientRect(),
      x = event.clientX - bounds.left,
      y = event.clientY - bounds.top;
    const row = Math.floor((y - 30 + scroll) / ROW_HEIGHT),
      time =
        view[0] +
        ((x - LABEL_WIDTH) / (width - LABEL_WIDTH - 15)) * (view[1] - view[0]);
    const span = hitTest(grid, row, time);
    return span
      ? { index: span.index, x: Math.min(x + 12, width - 220), y: y + 18 }
      : null;
  };
  return (
    <>
      <div className="timeline-toolbar">
        <div className="legend">
          {trace.dict.services.map((service, index) => (
            <span key={service}>
              <i style={{ background: COLORS[index % COLORS.length] }} />
              {service}
            </span>
          ))}
        </div>
        <div className="actions">
          <button
            className="ghost compact"
            aria-label="Zoom in"
            onClick={() =>
              setView(([start, end]) => {
                const margin = (end - start) / 4;
                return [start + margin, end - margin];
              })
            }
          >
            <Icon name="plus" size={14} />
          </button>
          <button
            className="ghost compact"
            onClick={() => setView([minimum, maximum])}
          >
            Reset
          </button>
          <button
            className="ghost compact"
            aria-label="Pan left"
            onClick={() =>
              setView(([a, b]) => [
                Math.max(minimum, a - (b - a) / 4),
                Math.max(minimum, a - (b - a) / 4) + (b - a),
              ])
            }
          >
            <Icon name="arrowLeft" size={14} />
          </button>
          <button
            className="ghost compact"
            aria-label="Pan right"
            onClick={() =>
              setView(([a, b]) => [
                Math.min(maximum, b + (b - a) / 4) - (b - a),
                Math.min(maximum, b + (b - a) / 4),
              ])
            }
          >
            <Icon name="arrow" size={14} />
          </button>
        </div>
      </div>
      <div
        ref={container}
        className="timeline-wrap"
        onScroll={(event) => setScroll(event.currentTarget.scrollTop)}
      >
        <canvas
          ref={canvas}
          className="timeline-canvas"
          style={{ width: "100%", height: HEIGHT }}
          aria-label="Trace waterfall; use the event cursor below for keyboard navigation"
          role="img"
          onPointerMove={(event) => setHover(locate(event))}
          onPointerLeave={() => setHover(null)}
          onClick={(event) => {
            const selected = locate(event);
            if (selected) onSelect(trace.spans.event_id[selected.index]);
          }}
        />
        <div style={{ height: Math.max(0, rows * ROW_HEIGHT - HEIGHT + 35) }} />
        {hover && (
          <div
            className="trace-tooltip"
            style={{ left: hover.x, top: hover.y + scroll }}
          >
            {trace.dict.types[trace.spans.type_idx[hover.index]]} ·{" "}
            {duration(trace.spans.dur_us[hover.index] / 1000)}
            <br />
            {trace.spans.status[hover.index]}
          </div>
        )}
      </div>
      <div
        className="trace-mobile"
        onScroll={(event) => setMobileScroll(event.currentTarget.scrollTop)}
      >
        <div style={{ height: positioned.length * 44, position: "relative" }}>
          {positioned
            .slice(
              Math.max(0, Math.floor(mobileScroll / 44) - 2),
              Math.floor(mobileScroll / 44) + 15,
            )
            .map((span, offset) => (
              <button
                key={span.index}
                style={{
                  position: "absolute",
                  top:
                    (Math.max(0, Math.floor(mobileScroll / 44) - 2) + offset) *
                    44,
                  left: Math.min(span.depth, 6) * 9,
                }}
                aria-pressed={selected === trace.spans.event_id[span.index]}
                onClick={() => onSelect(trace.spans.event_id[span.index])}
              >
                {trace.spans.status[span.index] === "error" ? "! " : ""}
                {
                  trace.dict.services[trace.spans.service_idx[span.index]]
                } · {duration(trace.spans.dur_us[span.index] / 1000)}
              </button>
            ))}
        </div>
      </div>
      <p className="hint">
        <span className="desktop-hint">
          {trace.spans.id.length.toLocaleString()} recorded spans · Scroll for
          lanes, zoom and pan for time · Red outline indicates an error
        </span>
        <span className="mobile-hint">
          Tap a span or use the event cursor to inspect its recorded state.
        </span>
      </p>
    </>
  );
}
