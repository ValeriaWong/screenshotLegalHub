import { SearchableSelect } from "../../components/collections";
import { Paged } from "../../components/collections";
import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type CasePlan, type Entity } from "../../api/client";
import { Button, Badge, Card } from "../../components/ui";
import { Feedback } from "../../components/feedback";
import { StatusIcon } from "../../components/icons";
import { useDetailRail } from "../../components/shell/DetailRail";
import { useI18n } from "../../i18n";
import { useUrlState } from "../../hooks/useUrlState";
export function Advanced({ caseId, readOnly = false }: { caseId: string; readOnly?: boolean }) {
  const { t } = useI18n();
  const rail = useDetailRail();
  const client = useQueryClient();
  const [runId, setRunId] = useUrlState("run");
  const [error, setError] = useState("");
  const [critical, setCritical] = useState(false);
  const [sse, setSse] = useState("");
  const plan = useQuery({
    queryKey: ["plan", caseId],
    queryFn: () => api<CasePlan>(`/cases/${caseId}/case-plan`),
    retry: false,
  });
  const runs = useQuery({
    queryKey: ["runs", caseId],
    queryFn: () => api<Record<string, any>[]>(`/cases/${caseId}/analysis/runs`),
  });
  const selected = runs.data?.find(r => r.id === runId)?.id || runs.data?.at(-1)?.id || "";
  const run = useQuery({
    queryKey: ["run", selected],
    queryFn: () => api<Record<string, any>>(`/runs/${selected}`),
    enabled: !!selected,
    refetchInterval: (q) =>
      q.state.data?.run.status === "RUNNING" ? 500 : false,
  });
  useEffect(() => {
    if (!selected) return;
    const stream = new EventSource(`/v1/runs/${selected}/events`);
    const update = (e: MessageEvent) => {
      if (e.type === "state-snapshot") {
        const data = JSON.parse(e.data);
        client.setQueryData(["run", selected], data);
        setSse("state-snapshot");
        if (["COMPLETED", "FAILED", "INTERRUPTED"].includes(data.run.status))
          stream.close();
      } else {
        setSse(e.type);
        void client.invalidateQueries({ queryKey: ["run", selected] });
        if (["run-completed", "run-failed"].includes(e.type)) {
          stream.close();
          void client.invalidateQueries();
        }
      }
    };
    [
      "state-snapshot",
      "run-started",
      "stage-started",
      "node-progress",
      "node-completed",
      "node-failed",
      "review-required",
      "review-resolved",
      "run-completed",
      "run-failed",
    ].forEach((name) => stream.addEventListener(name, update as EventListener));
    return () => stream.close();
  }, [selected, client]);
  async function action(fn: () => Promise<unknown>) {
    setError("");
    try {
      await fn();
      await client.invalidateQueries();
    } catch (e) {
      setError(String(e));
    }
  }
  const audits = run.data?.skill_runs || [];
  return (
    <>
      <div className="toolbar">
        <Button
          disabled={readOnly}
          onClick={() =>
            action(() => api(`/cases/${caseId}/matter-selection`, {}, "PUT"))
          }
        >
          {t("selectMatter")}
        </Button>
        <Button
          disabled={readOnly}
          onClick={() =>
            action(() => api(`/cases/${caseId}/analysis/compile`, {}))
          }
        >
          {t("compile")}
        </Button>
        <label>
          <input
            type="checkbox"
            checked={critical}
            onChange={(e) => setCritical(e.target.checked)}
          />
          {t("critical")}
        </label>
        <Button
          disabled={!plan.data || readOnly}
          onClick={() =>
            action(async () => {
              const r = await api<Record<string, any>>(
                `/cases/${caseId}/analysis/runs`,
                { critical_gate: critical },
              );
              setRunId(r.id);
            })
          }
        >
          {t("run")}
        </Button>
      </div>
      {error && <Feedback state="error" error={error} />}
      <SearchableSelect label={<>
        {t("runHistory")}

      </>} value={selected} onChange={(e) => setRunId(e.target.value)}>
          {runs.data?.map((r) => (
            <option key={r.id} value={r.id}>
              {r.started_at} · {r.status}
            </option>
          ))}
        </SearchableSelect>
      {run.data && (
        <Card>
          <h2>
            {t("runStatus")}:{" "}
            <span data-testid="run-status">{run.data.run.status}</span>
          </h2>
          <p data-testid="sse-state">SSE · {sse}</p>
          {run.data.run.error && <p role="alert">{run.data.run.error}</p>}
          {<Paged<Record<string, string>> items={run.data.gates} label="审核关卡" layout="block">{(pageItems) => pageItems.map((g: Record<string, string>) => (
            <div className="toolbar" key={g.id}>
              <Badge>
                {g.gate_id} · {g.status}
              </Badge>
              {g.status === "WAITING_REVIEW" && (
                <>
                  <Button
                    disabled={readOnly}
                    onClick={() =>
                      action(() =>
                        api(`/runs/${selected}/review-gates/${g.gate_id}`, {
                          action: "approve",
                        }),
                      )
                    }
                  >
                    {t("approve")}
                  </Button>
                  <Button
                    disabled={readOnly}
                    onClick={() =>
                      action(() =>
                        api(`/runs/${selected}/review-gates/${g.gate_id}`, {
                          action: "reject",
                        }),
                      )
                    }
                  >
                    {t("rejectGate")}
                  </Button>
                </>
              )}
            </div>
          ))}</Paged>}
        </Card>
      )}
      {plan.isPending ? (
        <Feedback state="loading" />
      ) : !plan.data ? (
        <Feedback state="notRun" />
      ) : (
        <>
          <h2>{t("graph")}</h2>
          <div className="dag" tabIndex={0}>
            {[...new Set(plan.data.nodes.map((n) => n.stage))].map((stage) => (
              <section key={stage}>
                <h3>Stage {stage}</h3>
                {<Paged items={plan
                  .data!.nodes.filter((n) => n.stage === stage)} label="阶段处理节点" layout="block">{(pageItems) => pageItems.map((node) => {
                    const audit = audits
                      .filter(
                        (a: Record<string, any>) => a.node_id === node.node_id,
                      )
                      .at(-1);
                    const status =
                      run.data?.node_states?.[node.node_id] ||
                      audit?.status ||
                      "PENDING";
                    return (
                      <Card key={node.node_id}>
                        <Badge>
                          <StatusIcon status={status} /> {status}
                        </Badge>
                        <h4>{node.capability}</h4>
                        <p>{node.resolved_skill_id}</p>
                        <p>← {node.depends_on.join(", ") || "∅"}</p>
                        {audit && (
                          <Button
                            onClick={() =>
                              rail.open({
                                type: "skillRun",
                                entity: {
                                  id: audit.id,
                                  kind: "skill_run",
                                  title: audit.node_id,
                                  details: audit,
                                } as Entity,
                              })
                            }
                          >
                            {t("audit")} · {t("attempt")} {audit.attempt} ·{" "}
                            {Number(audit.latency).toFixed(3)}s
                          </Button>
                        )}
                      </Card>
                    );
                  })}</Paged>}
              </section>
            ))}
          </div>
          <Card>
            <h2>{t("plan")}</h2>
            <code>{plan.data.plan_digest}</code>
            <p>
              {t("ruleVersion")}: {plan.data.matter_pack_version}
            </p>
            <pre tabIndex={0}>{JSON.stringify(plan.data, null, 2)}</pre>
          </Card>
        </>
      )}
      {run.error && <Feedback state="error" error={run.error.message} />}
    </>
  );
}
