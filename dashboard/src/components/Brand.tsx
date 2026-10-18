export function Brand() {
  return (
    <span className="brand">
      <svg
        className="brand-mark"
        width="30"
        height="30"
        viewBox="0 0 32 32"
        fill="none"
        aria-hidden="true"
      >
        <circle cx="16" cy="16" r="5" fill="currentColor" />
        <ellipse
          cx="16"
          cy="16"
          rx="14"
          ry="9"
          transform="rotate(-40 16 16)"
          stroke="currentColor"
          strokeWidth="1.6"
        />
        <circle
          cx="26.4"
          cy="7.3"
          r="3"
          fill="currentColor"
          stroke="var(--panel)"
          strokeWidth="1.8"
        />
      </svg>
      <span>
        tracelore<span className="brand-period">.</span>
      </span>
    </span>
  );
}
