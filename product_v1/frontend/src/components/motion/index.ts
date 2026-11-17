import { useSyncExternalStore } from "react";
const query = () => window.matchMedia("(prefers-reduced-motion: reduce)");
export function useReducedMotion() {
  return useSyncExternalStore(
    (callback) => {
      const m = query();
      m.addEventListener("change", callback);
      return () => m.removeEventListener("change", callback);
    },
    () => query().matches,
    () => true,
  );
}
