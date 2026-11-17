import { Paged } from "../../components/collections";
import { useQuery } from "@tanstack/react-query";
import { api, type Entity, type ProofGraph } from "../../api/client";
import { Card, Badge, Button } from "../../components/ui";
import { Feedback } from "../../components/feedback";
import { useDetailRail } from "../../components/shell/DetailRail";
import { Citations } from "../source-navigation";
import { useI18n } from "../../i18n";
export function Findings({
  caseId,
  kind,
}: {
  caseId: string;
  kind: "strategy" | "contradictions" | "gaps";
}) {
  const rail = useDetailRail();
  const { t } = useI18n();
  const graph = useQuery({
    queryKey: ["graph", caseId],
    queryFn: () => api<ProofGraph>(`/cases/${caseId}/proof-graph`),
  });
  const titleFor = (id: unknown) =>
    graph.data?.entities.find((e) => e.id === id)?.title || String(id);
  const q = useQuery({
    queryKey: [kind, caseId],
    queryFn: () => api<Entity[]>(`/cases/${caseId}/${kind}`),
  });
  if (q.isPending) return <Feedback state="loading" />;
  if (q.error)
    return (
      <Feedback
        state="error"
        error={q.error.message}
        retry={() => q.refetch()}
      />
    );
  if (!q.data.length) return <Feedback state="empty" />;
  return (
    <>
      {<Paged items={q.data} label="分析发现" layout="block" resetKey={caseId}>{(pageItems) => pageItems.map((e) => (
        <Card key={e.id}>
          <h2>
            <Button
              onClick={() =>
                rail.open({
                  type:
                    kind === "gaps"
                      ? "gap"
                      : kind === "contradictions"
                        ? "contradiction"
                        : "strategy",
                  entity: e,
                })
              }
            >
              {e.title}
            </Button>
          </h2>
          <Badge>{e.status}</Badge>
          <Badge>{e.review_status}</Badge>
          <p>
            {String(
              e.details.description ||
                e.details.why_needed ||
                e.details.explanation ||
                "",
            )}
          </p>
          {Boolean(e.details.fact_id) && (
            <p>
              <strong>{t("fact")}: </strong>
              {titleFor(e.details.fact_id)}
            </p>
          )}
          {Boolean(e.details.element_id) && (
            <p>
              <strong>{t("element")}: </strong>
              {titleFor(e.details.element_id)}
            </p>
          )}
          {Boolean(e.details.claim_id) && (
            <p>
              <strong>{t("claim")}: </strong>
              {titleFor(e.details.claim_id)}
            </p>
          )}
          {Boolean(e.details.fact_a) && (
            <p>
              <strong>{t("fact")}: </strong>
              {titleFor(e.details.fact_a)}
            </p>
          )}
          {Boolean(e.details.evidence_a) && (
            <p>
              <strong>{t("support")}: </strong>
              {titleFor(e.details.evidence_a)}
            </p>
          )}
          {Boolean(e.details.evidence_b) && (
            <p>
              <strong>{t("oppose")}: </strong>
              {titleFor(e.details.evidence_b)}
            </p>
          )}
          {Boolean(e.details.severity) && (
            <Badge>
              {t("warning")}: {String(e.details.severity)}
            </Badge>
          )}
          {Boolean(e.details.priority) && (
            <Badge>
              {t("warning")}: {String(e.details.priority)}
            </Badge>
          )}
          {Array.isArray(e.details.suggested_evidence_type) && (
            <p>
              <strong>{t("evidence")}: </strong>
              {e.details.suggested_evidence_type.join(" · ")}
            </p>
          )}
          {(
            [
              ["supporting_fact_ids", "support"],
              ["risk_fact_ids", "oppose"],
              ["gap_ids", "gaps"],
              ["counterargument_ids", "contradictions"],
              ["authority_ids", "rules"],
            ] as const
          ).map(
            ([field, label]) =>
              Array.isArray(e.details[field]) && (
                <div key={field}>
                  <strong>{t(label)}</strong>
                  <ul>
                    {<Paged items={(e.details[field] as string[])} label="关联记录" layout="list">{(pageItems) => pageItems.map((id) => (
                      <li key={id}>{titleFor(id)}</li>
                    ))}</Paged>}
                  </ul>
                </div>
              ),
          )}
          <Citations caseId={caseId} refs={e.source_refs || []} />
        </Card>
      ))}</Paged>}
    </>
  );
}
