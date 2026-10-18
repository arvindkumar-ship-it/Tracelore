import type { SVGProps } from "react";

const paths = {
  activity: "M3 12h4l3-8 4 16 3-8h4",
  incidents:
    "M12 8v4m0 4h.01M10.3 3.9 2.5 17.4A2 2 0 0 0 4.2 20h15.6a2 2 0 0 0 1.7-2.6L13.7 3.9a2 2 0 0 0-3.4 0Z",
  clock: "M12 8v4l3 2M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z",
  graph:
    "M9 5h6M5 9v6m14-6v6M9 19h6M3 3h6v6H3V3Zm12 0h6v6h-6V3ZM3 15h6v6H3v-6Zm12 0h6v6h-6v-6Z",
  flask:
    "M9 3h6m-5 0v6l-5.5 9A2 2 0 0 0 6.2 21h11.6a2 2 0 0 0 1.7-3L14 9V3M8 14h8",
  settings:
    "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Zm-8.4 9 1.2 2 2.7-.3 2 1.2 1.1 2.1h2.8l1.1-2.1 2-1.2 2.7.3 1.2-2-1.5-2.3v-2.4l1.5-2.3-1.2-2-2.7.3-2-1.2L13.4 5h-2.8L9.5 7.1l-2 1.2-2.7-.3-1.2 2 1.5 2.3v2.4L3.6 17Z",
  arrow: "M5 12h14m-5-5 5 5-5 5",
  arrowLeft: "M19 12H5m5-5-5 5 5 5",
  chevron: "m9 5 7 7-7 7",
  external:
    "M14 3h7v7m0-7L10 14M10 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-5",
  plus: "M12 5v14M5 12h14",
  search: "m21 21-5-5M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0Z",
  layers: "m12 3 10 5-10 5L2 8l10-5Zm-10 9 10 5 10-5M2 16l10 5 10-5",
  logout: "M9 4H5a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h4m5-12 4 4-4 4m-5-4h12",
  menu: "M4 6h16M4 12h16M4 18h16",
  close: "m6 6 12 12M6 18 18 6",
  check: "m5 12 4 4L19 6",
  info: "M12 11v6m0-10h.01M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z",
  refresh: "M20 7v5h-5M4 17v-5h5m11 0a8 8 0 0 0-13.7-6M4 12a8 8 0 0 0 13.7 6",
  server: "M4 3h16v7H4V3Zm0 11h16v7H4v-7ZM7 6.5h.01M7 17.5h.01",
  key: "m14 10 7-7m-3 3 3 3m-6 0 3 3M15 15a6 6 0 1 1-12 0 6 6 0 0 1 12 0Z",
  shield: "M12 3 3 7v5c0 5 9 9 9 9s9-4 9-9V7l-9-4Zm-4 9 3 3 5-6",
  code: "m8 6-6 6 6 6m8-12 6 6-6 6m-3-15-2 18",
  copy: "M9 9h12v12H9V9ZM15 9V3H3v12h6",
  database:
    "M20 6c0 2.2-3.6 4-8 4s-8-1.8-8-4 3.6-4 8-4 8 1.8 8 4Zm0 0v12c0 2.2-3.6 4-8 4s-8-1.8-8-4V6m0 6c0 2.2 3.6 4 8 4s8-1.8 8-4",
  eye: "M2 12s3-7 10-7 10 7 10 7-3 7-10 7S2 12 2 12Zm13 0a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z",
} as const;

export type IconName = keyof typeof paths;
export function Icon({
  name,
  size = 18,
  ...props
}: SVGProps<SVGSVGElement> & { name: IconName; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...props}
    >
      <path d={paths[name]} />
    </svg>
  );
}
