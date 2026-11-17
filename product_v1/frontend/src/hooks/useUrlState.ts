import { useState } from "react";
export function useUrlState(key: string, fallback = "") {
  const [value, set] = useState(
    new URLSearchParams(location.search).get(key) || fallback,
  );
  return [
    value,
    (next: string) => {
      const url = new URL(location.href);
      if (next) url.searchParams.set(key, next);
      else url.searchParams.delete(key);
      history.replaceState({}, "", url);
      set(next);
    },
  ] as const;
}
