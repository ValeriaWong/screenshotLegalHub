import {
  createContext,
  useContext,
  useState,
  useRef,
  useEffect,
  type ReactNode,
} from "react";
import type { Entity, EvidenceItem, SourceRef } from "../../api/client";
import { Button } from "../ui";
import { useI18n } from "../../i18n";
import { SourceViewer } from "../../features/source-navigation/SourceViewer";
export type ViewerContent = {
  type: "image" | "pdf" | "audio" | "video" | "text";
  url: string;
  filename: string;
  page?: number;
  timestamp?: number;
  bbox?: number[];
  regions?: SourceRef[];
  highlightText?: string;
  coordinateSpace?: "pixels" | "normalized_1000";
  originalUrl?: string;
  width?: number;
  height?: number;
};
export type DetailContentDescriptor =
  | { type: "source"; viewer: ViewerContent; source: SourceRef }
  | { type: "evidence"; evidence: EvidenceItem; viewer: ViewerContent }
  | {
      type:
        | "message"
        | "event"
        | "claim"
        | "fact"
        | "gap"
        | "contradiction"
        | "strategy"
        | "skillRun";
      entity: Entity;
    };
type Rail = {
  open: (content: DetailContentDescriptor) => void;
  close: () => void;
  content: DetailContentDescriptor | null;
};
const RailContext = createContext<Rail>({
  open: () => {},
  close: () => {},
  content: null,
});
export const useDetailRail = () => useContext(RailContext);
export function DetailRailProvider({ children }: { children: ReactNode }) {
  const [content, setContent] = useState<DetailContentDescriptor | null>(null);
  return (
    <RailContext.Provider
      value={{ content, open: setContent, close: () => setContent(null) }}
    >
      {children}
    </RailContext.Provider>
  );
}
export function DetailRail() {
  const { content, close } = useDetailRail();
  const { t } = useI18n();
  const [collapsed, setCollapsed] = useState(false);
  const [width, setWidth] = useState(
    Math.max(
      300,
      Math.min(720, Number(localStorage.getItem("railWidth")) || 420),
    ),
  );
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    if (content) {
      setCollapsed(false);
      heading.current?.focus();
    }
  }, [content]);
  if (!content) return null;
  return (
    <aside
      className={"detail-rail " + (collapsed ? "collapsed" : "")}
      style={{ width: collapsed ? 58 : width }}
      aria-label={t("detail")}
      onKeyDown={(e) => {
        if (e.key === "Escape") close();
      }}
    >
      <div className="rail-header">
        <h2 tabIndex={-1} ref={heading}>
          {collapsed ? "" : t("detail")}
        </h2>
        <Button
          aria-label={collapsed ? t("expand") : t("collapse")}
          onClick={() => setCollapsed(!collapsed)}
        >
          {collapsed ? "‹" : "›"}
        </Button>
        <Button aria-label={t("close")} onClick={close}>
          ×
        </Button>
      </div>
      {!collapsed && (
        <>
          <label className="rail-resize">
            {t("resize")}
            <input
              type="range"
              min="300"
              max="720"
              value={width}
              onChange={(e) => {
                setWidth(Number(e.target.value));
                localStorage.setItem("railWidth", e.target.value);
              }}
            />
          </label>
          <div className="rail-body">
            {"viewer" in content ? (
              <SourceViewer key={content.viewer.url + ":" + (content.viewer.bbox?.join(",") || "all")} content={content.viewer} />
            ) : (
              <>
                <h3>{content.entity.title}</h3>
                <pre tabIndex={0}>
                  {JSON.stringify(content.entity, null, 2)}
                </pre>
              </>
            )}
          </div>
        </>
      )}
    </aside>
  );
}
