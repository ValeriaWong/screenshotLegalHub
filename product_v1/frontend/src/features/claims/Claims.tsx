import { Paged } from "../../components/collections";
import { useQuery } from "@tanstack/react-query";
import { api, type MatrixRow } from "../../api/client";
import { Card, Badge } from "../../components/ui";
import { Feedback } from "../../components/feedback";
import { Citations } from "../source-navigation";
import { useI18n } from "../../i18n";
export function Claims({ caseId }: { caseId: string }) {
  const { t } = useI18n();
  const q = useQuery({
    queryKey: ["matrix", caseId],
    queryFn: () => api<MatrixRow[]>(`/cases/${caseId}/proof-matrix`),
  });
  if (q.isPending) return <Feedback state="loading" />;
  if (q.error) return <Feedback state="error" error={q.error.message} />;
  if (!q.data.length) return <Feedback state="notRun" />;
  return (
    <>
      {<Paged items={[...new Set(q.data.map((r) => r.claim.id))]} label="案件主张" layout="block">{(pageItems) => pageItems.map((id) => (
        <Card key={id}>
          <h2>{q.data.find((r) => r.claim.id === id)?.claim.title}</h2>
          {<Paged items={q.data
            .filter((r) => r.claim.id === id)} label="主张事实" layout="block">{(pageItems) => pageItems.map((r) => (
              <section className="claim-element" key={r.fact.id}>
                <h3>{r.element.title}</h3>
                <p>{r.fact.title}</p>
                <Badge>{r.fact.status}</Badge>
                <Badge>{r.fact.review_status}</Badge>
                <p>
                  {t("burden")}: {r.burden?.title}
                </p>
                <p>
                  {t("support")}: {r.supporting.length} · {t("oppose")}:{" "}
                  {r.contradicting.length} · {t("gap")}: {r.gaps.length}
                </p>
                <Citations caseId={caseId} refs={r.fact.source_refs || []} />
              </section>
            ))}</Paged>}
        </Card>
      ))}</Paged>}
    </>
  );
}
