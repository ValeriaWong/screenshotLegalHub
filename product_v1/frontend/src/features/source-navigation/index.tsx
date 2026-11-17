import { useState } from "react";
import { Paged } from "../../components/collections";
import { useQuery } from "@tanstack/react-query";
import { api, type EvidenceItem, type SourceRef } from "../../api/client";
import {
  useDetailRail,
  type ViewerContent,
} from "../../components/shell/DetailRail";
import { Button } from "../../components/ui";
import { useI18n } from "../../i18n";
export type CitationDescriptor = {
  sourceRefId: string;
  evidenceId: string;
  imageId?: string;
  messageId?: string;
  page?: number;
  bbox?: number[];
  quote?: string;
};
export function viewerFor(
  caseId: string,
  evidence: EvidenceItem,
  ref?: SourceRef,
  allRefs?: SourceRef[],
): ViewerContent {
  return {
    type: evidence.mime_type.startsWith("image/")
      ? "image"
      : evidence.mime_type === "application/pdf"
        ? "pdf"
        : "text",
    url: `/v1/cases/${caseId}/evidence/${evidence.id}/file`,
    filename: evidence.filename,
    page: ref?.evidence_page ?? undefined,
    bbox: ref?.bbox || undefined,
    regions: allRefs?.filter(r => r.evidence_id === evidence.id && r.bbox),
    highlightText: ref?.quote,
    width: evidence.width || undefined,
    height: evidence.height || undefined,
  };
}
export function useSourceNavigation(caseId: string) {
  const rail = useDetailRail();
  const [resolveError,setResolveError]=useState<Error|null>(null);
  const evidence = useQuery({
    queryKey: ["evidence", caseId],
    queryFn: () => api<EvidenceItem[]>(`/cases/${caseId}/evidence`),
  });
  const refs = useQuery({
    queryKey: ["refs", caseId],
    queryFn: () => api<SourceRef[]>(`/cases/${caseId}/source-refs`),
  });
  return {
    ready: !!evidence.data && !!refs.data,
    error: resolveError || evidence.error || refs.error,
    open: async (id: string) => {
      setResolveError(null);
      try {
      const resolution=await api<{source:SourceRef}>("/cases/"+caseId+"/resolve-source",{source_ref_id:id});
      const ref = resolution.source;
      const item = evidence.data?.find((e) => e.id === ref?.evidence_id);
      if (ref?.source_kind === "document" && ref.original_url) {
        rail.open({ type: "source", source: ref, viewer: {
          type: ref.page_kind === "physical_page" && ref.preview_url ? "image" : "text",
          url: ref.page_kind === "physical_page" && ref.preview_url ? ref.preview_url : ref.original_url,
          originalUrl: ref.original_url, filename: "文档原文 · " + (ref.page_no || 1), page: ref.page_no || undefined,
          bbox: ref.bbox || undefined, coordinateSpace: ref.coordinate_space || undefined,
          highlightText: ref.quote || ref.text,
        } });
      } else if (ref && item)
        rail.open({
          type: "source",
          source: ref,
          viewer: viewerFor(caseId, item, ref, refs.data),
        });
      } catch(e) { setResolveError(e instanceof Error ? e : new Error(String(e))); }
    },
  };
}
export function Citations({
  caseId,
  refs,
}: {
  caseId: string;
  refs: string[];
}) {
  const nav = useSourceNavigation(caseId);
  const { t } = useI18n();
  return (
    <div className="citations">
      {nav.error && <p role="alert">{nav.error.message}</p>}
      {<Paged items={refs} label="来源引用" layout="block" pageSize={10}>{(pageItems, pageOffset) => pageItems.map((ref, pageIndex) => { const i = pageIndex + pageOffset; return ((
        <Button
          key={ref}
          disabled={!nav.ready}
          title={nav.error?.message}
          aria-label={`${t("citation")} ${i + 1}`}
          onClick={() => nav.open(ref)}
        >
          {t("citation")} {i + 1}
        </Button>
      )); })}</Paged>}
    </div>
  );
}
