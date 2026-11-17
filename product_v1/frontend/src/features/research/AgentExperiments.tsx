import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type CaseRecord, type ModelConfig } from "../../api/client";
import { Button, Card, Input } from "../../components/ui";
import { Paged, SearchableSelect } from "../../components/collections";
import { ErrorText, JsonView, Status } from "./shared";

interface Method { reproduction_name?: string; id: string; title: string; priority: string; implementation_status: string; requires_matterpack: boolean; requires_factor_hierarchy: boolean; builds_hierarchy_from_frozen_law?: boolean; paper_claim: string }
interface Document { id: string; filename: string; status: string; parser: string }
interface Run { reproduction_name?: string; id: string; case_title: string; method_id?: string; method?: Method; status: string; demo: boolean; name: string; usage?: { model_calls: number; tool_calls: number; input_tokens: number; output_tokens: number; cost: number | null; missing_usage_calls: number }; error?: { message: string }; output?: { summary: string; uncertainties: string[]; facts: { id: string; statement: string; citations: { source_ref_id: string; quote: string; start: number; end: number }[] }[] } }
interface Source { id: string; original_url: string; preview_url?: string; page_no?: number; source_locator: string; text: string; page_kind: string }
interface Result { run: Run; steps: { id: string; stage: string; status: string; messages: unknown; response?: unknown }[]; tools: unknown[]; sources: Source[]; graph: unknown; staleness: { stale: boolean; reasons: string[] } }
interface Preview { input_digest: string; sources: number; estimated_call_ceiling: number; methods: { id: string; maximum_model_calls: number; may_exhaust_budget: boolean }[]; limitations: string[] }
interface Comparison { fixed_factors_match: boolean; mismatches: string[]; measured_usage_comparable: boolean; exclusion_reasons: string[]; quality_reason: string }
const supportsThinkingControl = (url?: string) => { try { return ["aiping.cn", "www.aiping.cn"].includes(new URL(url || "").hostname); } catch { return false; } };
const toggle = (list: string[], id: string) => list.includes(id) ? list.filter(x => x !== id) : [...list, id];
export function AgentExperiments() {
  const client = useQueryClient();
  const [caseId, setCaseId] = useState(new URLSearchParams(location.search).get("case") || "");
  const [documentIds, setDocumentIds] = useState<string[]>([]), [methodIds, setMethodIds] = useState(["E00", "E02"]);
  const [modelId, setModelId] = useState("demo"), [revision, setRevision] = useState("");
  const [thinking, setThinking] = useState("default"), [outputPerCall, setOutputPerCall] = useState(2000);
  const [name, setName] = useState("案件方法对照"), [goal, setGoal] = useState("整理材料中的待证事实、支持与反证，明确不确定性并逐条引用原文。");
  const [group, setGroup] = useState(""), [split, setSplit] = useState("development"), [draft, setDraft] = useState(false);
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [calls, setCalls] = useState(12), [tools, setTools] = useState(16), [inputTokens, setInputTokens] = useState(200000), [outputTokens, setOutputTokens] = useState(20000), [seconds, setSeconds] = useState(300);
  const [rounds, setRounds] = useState(1), [topK, setTopK] = useState(5);
  const [labVariant, setLabVariant] = useState("react");
  const [selected, setSelected] = useState(new URLSearchParams(location.search).get("agent_run") || ""), [compareIds, setCompareIds] = useState<string[]>([]), [comparison, setComparison] = useState<Comparison | null>(null);
  const [preview, setPreview] = useState<{ value: Preview; request: string } | null>(null), [error, setError] = useState(""), [busy, setBusy] = useState(false), [notice, setNotice] = useState("");
  const cases = useQuery({ queryKey: ["cases"], queryFn: () => api<CaseRecord[]>("/cases") });
  const methods = useQuery({ queryKey: ["agent-methods"], queryFn: () => api<{ candidates: Method[] }>("/evaluation/agent-methods") });
  const documents = useQuery({ queryKey: ["documents", caseId], queryFn: () => api<Document[]>("/cases/" + caseId + "/documents"), enabled: !!caseId });
  const models = useQuery({ queryKey: ["models"], queryFn: () => api<ModelConfig[]>("/settings/models") });
  const runs = useQuery({ queryKey: ["agent-runs"], queryFn: () => api<Run[]>("/evaluation/agent-runs"), refetchInterval: 2500 });
  const result = useQuery({ queryKey: ["agent-result", selected], queryFn: () => api<Result>("/evaluation/agent-runs/" + selected), enabled: !!selected, refetchInterval: q => ["queued", "running"].includes(q.state.data?.run.status || "") ? 1500 : false });
  const thinkingSupported = supportsThinkingControl(models.data?.find(m => m.id === modelId)?.base_url);
  const payload = { ...(methodIds.includes("E23") ? { method_options: { legalagentbench_variant: labVariant } } : {}), inference_options: { enable_thinking: thinkingSupported && thinking !== "default" ? thinking === "on" : null }, case_id: caseId, name, goal, document_ids: documentIds, method_ids: methodIds, model_id: modelId, model_revision: revision, case_group_id: group || caseId, split, law_effective_date: date, allow_draft_matter: draft, debate_rounds: rounds, retrieval_top_k: topK, budget: { max_model_calls: calls, max_tool_calls: tools, max_input_tokens: inputTokens, max_output_tokens: outputTokens, max_wall_time_s: seconds, max_output_per_call: outputPerCall } };
  const request = JSON.stringify(payload), validPreview = preview?.request === request;
  async function action(fn: () => Promise<void>) { setBusy(true); setError(""); try { await fn(); } catch (e) { setError(String(e)); } finally { setBusy(false); } }
  return <>
    <Card><h2>案件方法对照与论文实验</h2><p>使用同一份冻结材料比较分析方法。离线演练检查流程；模型结果须有专家金标才能评估法律质量。新方法均标注复现范围。</p>
      <form className="research-form" onSubmit={e => { e.preventDefault(); void action(async () => { const value = await api<Preview>("/evaluation/agent-preview", { ...payload, idempotency_key: crypto.randomUUID() }); setPreview({ value, request }); setNotice("已检查输入与调用上限，请核对后启动。"); }); }}>
        <div className="research-grid-3"><SearchableSelect label="案件" required value={caseId} onChange={e => { setCaseId(e.target.value); setDocumentIds([]); setPreview(null); }}><option value="">选择案件</option>{cases.data?.map(c => <option key={c.id} value={c.id}>{c.title}</option>)}</SearchableSelect>
          <label>实验名称<Input required value={name} onChange={e => setName(e.target.value)} /></label>
          <SearchableSelect label="分析模型" value={modelId} onChange={e => { setModelId(e.target.value); setThinking("default"); }}><option value="demo">离线演练（不计模型能力分）</option>{models.data?.map(m => <option key={m.id} value={m.id} disabled={!m.allow_external_egress}>{m.name} · {m.model_name}{!m.allow_external_egress && " · 请求未启用"}</option>)}</SearchableSelect>
          <label>模型精确版本<Input value={revision} onChange={e => setRevision(e.target.value)} placeholder="应与供应商返回型号一致" /></label>
          <label>法律适用日期<Input type="date" required value={date} onChange={e => setDate(e.target.value)} /></label>
          <label>数据划分<select value={split} onChange={e => setSplit(e.target.value)}><option value="development">开发诊断</option><option value="holdout">留出评测</option></select></label>
          <label>案件组标识<Input value={group} onChange={e => setGroup(e.target.value)} placeholder="默认使用案件编号；同一案件衍生资料须同组" /></label>
        </div>
        <label>分析目标<textarea required value={goal} onChange={e => setGoal(e.target.value)} /></label>
        <fieldset><legend>选择已解析文档（当前聊天转录自动纳入）</legend>{!documents.data?.length && <p>尚无文档，可先到案件资料工作区上传并解析。</p>}<Paged items={documents.data} label="候选资料" layout="block">{items => items.map(d => <label className="research-check" key={d.id}><Input type="checkbox" disabled={d.status !== "complete"} checked={documentIds.includes(d.id)} onChange={() => setDocumentIds(toggle(documentIds, d.id))} />{d.filename} · {d.status === "complete" ? "解析完成" : "尚未解析完成"}</label>)}</Paged></fieldset>
        <fieldset><legend>方法（需要模板的方法须先在案件中选择领域）</legend><Paged items={methods.data?.candidates} label="研究方法" layout="block" pageSize={25}>{items => items.map(m => <label className="research-check" key={m.id}><Input type="checkbox" disabled={m.implementation_status !== "implemented"} checked={methodIds.includes(m.id)} onChange={() => setMethodIds(toggle(methodIds, m.id))} /><span>{m.id} · {m.title} · {m.priority}{m.implementation_status !== "implemented" ? " · 尚未实现" : m.builds_hierarchy_from_frozen_law ? " · 从冻结法源构建未复核层级" : m.requires_factor_hierarchy ? " · 需要独立指南层级" : m.requires_matterpack ? " · 需要领域模板" : ""}<small>{m.reproduction_name && " · " + m.reproduction_name} · {m.paper_claim}</small></span></label>)}</Paged></fieldset>
        <label className="research-check"><Input type="checkbox" checked={draft} onChange={e => setDraft(e.target.checked)} />允许未复核领域模板用于开发诊断（不能用于留出评分）</label>
        <details open><summary>统一预算与消融参数</summary><div className="research-grid-3">
          <label>每方法最多模型调用<Input type="number" min={1} max={30} value={calls} onChange={e => setCalls(Number(e.target.value))} /></label><label>每方法最多工具调用<Input type="number" min={0} max={50} value={tools} onChange={e => setTools(Number(e.target.value))} /></label>
          <label>输入 token 总上限<Input type="number" min={100} max={1000000} value={inputTokens} onChange={e => setInputTokens(Number(e.target.value))} /></label><label>输出 token 总上限<Input type="number" min={100} max={200000} value={outputTokens} onChange={e => setOutputTokens(Number(e.target.value))} /></label><label>每方法总时长（秒）<Input type="number" min={5} max={1800} value={seconds} onChange={e => setSeconds(Number(e.target.value))} /></label>
          <label>单次输出 token 上限<Input type="number" min={100} max={10000} value={outputPerCall} onChange={e => setOutputPerCall(Number(e.target.value))} /></label>
          {thinkingSupported && <div><label>思考模式<select value={thinking} onChange={e => setThinking(e.target.value)} aria-describedby="experiment-thinking-help"><option value="default">供应商默认</option><option value="off">关闭</option><option value="on">开启</option></select></label><small id="experiment-thinking-help">随实验冻结保存；改变模式后须重新检查预算，不应将不同模式作为等条件对照。</small></div>}
          {methodIds.includes("E23") && <label>LegalAgentBench 控制器<select value={labVariant} onChange={e => setLabVariant(e.target.value)}><option value="react">ReAct</option><option value="plan_and_solve">Plan-and-Solve</option><option value="plan_and_execute">Plan-and-Execute</option></select></label>}<label>E09 辩论轮数<Input type="number" min={0} max={3} value={rounds} onChange={e => setRounds(Number(e.target.value))} /></label><label>检索数量<Input type="number" min={1} max={10} value={topK} onChange={e => setTopK(Number(e.target.value))} /></label>
        </div></details>
        <Button disabled={busy || !caseId || !methodIds.length}>检查输入与预算</Button>
      </form>
      {validPreview && preview && <section aria-label="运行预览"><p>冻结来源 {preview.value.sources} 条；本批最多 {preview.value.estimated_call_ceiling} 次模型调用。{preview.value.methods.some(m => m.may_exhaust_budget) && "部分方法的完整路径可能超过预算，届时会停止并记录失败。"}</p><Button disabled={busy} aria-busy={busy} onClick={() => action(async () => { const cohort = await api<{ run_ids: string[] }>("/evaluation/agent-runs", { ...payload, expected_input_digest: preview.value.input_digest, idempotency_key: crypto.randomUUID() }); setSelected(cohort.run_ids[0]); setCompareIds(cohort.run_ids); setPreview(null); setNotice("实验已加入队列，结果会自动刷新。"); await client.invalidateQueries({ queryKey: ["agent-runs"] }); })}>{modelId === "demo" ? "启动离线演练" : "启动所选模型实验（按调用计费）"}</Button></section>}
      {busy && <p role="status">正在处理，请稍候…</p>}{notice && <p role="status">{notice}</p>}
      <ErrorText error={error || cases.error || documents.error || methods.error || models.error} />
    </Card>
    <Card><h2>实验记录与对照</h2><ErrorText error={runs.error} /><Paged items={runs.data} label="方法运行" layout="block">{items => <div className="research-table-wrap" tabIndex={0}><table><thead><tr><th>比较</th><th>案件 / 方法</th><th>状态</th><th>模型 / 工具调用</th><th>结果</th></tr></thead><tbody>{items.map(r => <tr key={r.id}><td><Input type="checkbox" aria-label={"比较 " + r.case_title + " " + r.method_id} checked={compareIds.includes(r.id)} onChange={() => { setCompareIds(toggle(compareIds, r.id)); setComparison(null); }} /></td><td>{r.case_title} · {r.method_id}{r.reproduction_name && " · " + r.reproduction_name}{r.demo && " · 演练"}</td><td><Status value={r.status} /></td><td>{r.usage?.model_calls ?? 0} / {r.usage?.tool_calls ?? 0}</td><td><Button onClick={() => setSelected(r.id)}>查看轨迹与引用</Button></td></tr>)}</tbody></table></div>}</Paged>
      <Button disabled={busy || !compareIds.length} onClick={() => action(async () => setComparison(await api<Comparison>("/evaluation/agent-comparison?" + new URLSearchParams({ ids: compareIds.join(",") }))))}>检查所选对照（{compareIds.length}）</Button>
      {comparison && <section aria-label="对照条件"><p>{comparison.fixed_factors_match ? "固定因素一致。" : "固定因素不一致：" + comparison.mismatches.join("、")}{comparison.measured_usage_comparable ? "用量记录满足本次比较条件。" : "当前不能作等条件用量比较。"}</p><p>{comparison.exclusion_reasons.join("；")}</p><p>{comparison.quality_reason}</p></section>}
    </Card>
    {result.data && <Card><h2>{result.data.run.method?.id}{result.data.run.method?.reproduction_name && " · " + result.data.run.method.reproduction_name} · <Status value={result.data.run.status} /></h2><ErrorText error={result.error || result.data.run.error?.message} />{result.data.staleness.stale && <p role="alert">{result.data.staleness.reasons.join("；")}</p>}<p>{result.data.run.output?.summary}</p>
      <Paged items={result.data.run.output?.facts} label="有来源的事实" layout="block">{items => items.map(f => <article key={f.id}><h3>{f.statement}</h3>{f.citations.map((c, i) => { const s = result.data!.sources.find(s => s.id === c.source_ref_id); return <blockquote key={i}>{c.quote}<br />{s && <a href={s.original_url + (s.page_kind === "physical_page" ? "#page=" + s.page_no : "")} target="_blank" rel="noreferrer">查看原文 · 字符 {c.start}–{c.end}{s.page_no ? " · 第 " + s.page_no + (s.page_kind === "logical_unit" ? " 逻辑单元" : " 页") : ""}</a>}</blockquote>; })}</article>)}</Paged>
      <p>{result.data.run.output?.uncertainties.join("；")}</p><a href={"/v1/evaluation/agent-runs/" + selected + "/export"}>导出论文实验原始记录（含完整输入提示与响应）</a>
      <details><summary>模型调用、工具与证据关系</summary><JsonView value={{ usage: result.data.run.usage, steps: result.data.steps, tools: result.data.tools, graph: result.data.graph }} /></details>
    </Card>}
  </>;
}
