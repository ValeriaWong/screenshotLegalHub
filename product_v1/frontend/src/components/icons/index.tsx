const paths = {
  scales: "M12 3v18M5 21h14M5 7h14M4 7l-3 7h6L4 7Zm16 0-3 7h6l-3-7ZM1 14a3 3 0 0 0 6 0m10 0a3 3 0 0 0 6 0M9 5h6",
  overview: "M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z",
  edit: "m16 3 5 5M4 20l4-1L21 6a2.1 2.1 0 0 0-3-3L5 16l-1 4ZM13 4H4a1 1 0 0 0-1 1v16h16v-9",
  timeline: "M5 3v18M9 5h11M9 12h8M9 19h11M3 5h4M3 12h4M3 19h4",
  presentation: "M3 4h18v13H3zM12 17v4M8 21h8M7 12l3-3 3 2 4-5",
  evaluation: "M4 20V10h4v10M10 20V4h4v16M16 20v-7h4v7M2 20h20",
  studio: "M13 2 4 14h7l-1 8 10-12h-8l1-8Z",
  review: "M14 3H5a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1V9l-6-6ZM14 3v6h6M8 15l3 3 5-6",
  folder: "M3 7V5a1 1 0 0 1 1-1h5l2 3h9a1 1 0 0 1 1 1v11a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V7Z",
  arrow: "M5 12h14m-5-5 5 5-5 5",
  logout: "M9 4H4v16h5M10 12h11m-4-4 4 4-4 4",
  history: "M3 4v5h5M3 9a9 9 0 1 1 0 7M12 7v5l3 2",
  check: "m5 12 4 4L19 6",
  alert: "m12 3 10 18H2L12 3ZM12 9v5M12 17h.01",
  clock: "M12 8v5l3 2M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z",
  circle: "M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z",
  file: "M14 3H5v18h14V8l-5-5ZM14 3v5h5M8 12h8M8 16h6",
} as const;
export type IconName = keyof typeof paths;
export function Icon({ name, size = 20 }: { name: IconName; size?: number }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false" className="ui-icon"><path d={paths[name]} /></svg>;
}
export function Logo() {
  return <span className="logo" aria-hidden="true"><Icon name="scales" size={25} /></span>;
}
export function StatusIcon({ status }: { status: string }) {
  return <Icon name={status === "COMPLETED" ? "check" : status === "FAILED" ? "alert" : status === "WAITING_REVIEW" ? "clock" : "circle"} size={16} />;
}
