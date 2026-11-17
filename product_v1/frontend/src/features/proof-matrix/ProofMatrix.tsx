import { Paged } from "../../components/collections";
import { useQuery } from "@tanstack/react-query";
import { api, type MatrixRow } from "../../api/client";
import { Badge, Button } from "../../components/ui";
import { Feedback } from "../../components/feedback";
import { Citations } from "../source-navigation";
import { useDetailRail } from "../../components/shell/DetailRail";
import { useI18n } from "../../i18n";
export function ProofMatrix({ caseId }: { caseId: string }) {
  const { t } = useI18n();
  const rail = useDetailRail();
  const query = useQuery({
    queryKey: ["matrix", caseId],
    queryFn: () => api<MatrixRow[]>(`/cases/${caseId}/proof-matrix`),
  });
  if (query.isPending) return <Feedback state="loading" />;
  if (query.error)
    return (
      <Feedback
        state="error"
        error={query.error.message}
        retry={() => query.refetch()}
      />
    );
  if (!query.data.length) return <Feedback state="notRun" />;
  return (
    <Paged items={query.data} label="证明矩阵" layout="block" resetKey={caseId}>{(visibleRows8) => <><div className="table-scroll" tabIndex={0}>
      <table>
        <caption>{t("matrix")}</caption>
        <thead>
          <tr>
            {(
              [
                "claim",
                "element",
                "fact",
                "burden",
                "support",
                "oppose",
                "gap",
                "strength",
                "reviewStatus",
              ] as const
            ).map((k) => (
              <th scope="col" key={k}>
                {t(k)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {visibleRows8.map((row) => (
            <tr key={row.fact.id}>
              <td>{row.claim.title}</td>
              <td>{row.element.title}</td>
              <td>
                <Button
                  onClick={() => rail.open({ type: "fact", entity: row.fact })}
                >
                  {row.fact.title}
                </Button>
                <Badge>{row.fact.status}</Badge>
              </td>
              <td>{row.burden?.title}</td>
              <td>
                {<Paged items={row.supporting} label="支持证据" layout="block">{(visibleRows8) => visibleRows8.map((link) => (
                  <div key={link.id}>
                    {link.title}
                    <Citations caseId={caseId} refs={link.source_refs || []} />
                  </div>
                ))}</Paged>}
              </td>
              <td>
                {<Paged items={row.contradicting} label="反对证据" layout="block">{(visibleRows8) => visibleRows8.map((link) => (
                  <div key={link.id}>
                    {link.title}
                    <Citations caseId={caseId} refs={link.source_refs || []} />
                  </div>
                ))}</Paged>}
              </td>
              <td>
                {<Paged items={row.gaps} label="证据缺口" layout="block">{(visibleRows8) => visibleRows8.map((g) => (
                  <p key={g.id}>{g.title}</p>
                ))}</Paged>}
              </td>
              <td>{row.strength}</td>
              <td>
                <Badge>{row.fact.review_status}</Badge>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div></>}</Paged>
  );
}
