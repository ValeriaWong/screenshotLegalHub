import { Leaderboard } from "./Leaderboard";
import { AgentExperiments } from "./AgentExperiments";
import { SearchableSelect } from "../../components/collections";
import { Paged } from "../../components/collections";
import { BenchmarkPanel } from "./BenchmarkPanel";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, Card, Input } from "../../components/ui";
import { EvaluationHistory } from "./EvaluationHistory";
import { ModelSettings } from "../settings/ModelSettings";
import type { ModelConfig } from "../../api/client";
import { api, key, num, type EvalRun, type Release, type Job, type Sample } from "./client";
import { term } from "./presentation";
import { revealInvalidField, ErrorText, JobsPanel, JsonView, Status, FailureNotice } from "./shared";
interface Attempt { id: string; task_id: string; request_id?: string; status: string; answer?: string; scoring_status: string; score: number | null; latency_ms?: number; cost?: number; error?: { category: string; message: string; retryable: boolean }; response?: Record<string, unknown> }
interface ReportModel { model: { id: string; name: string; endpoint: string; model: string; billing?: { currency?: string } }; total: number; completed: number; failed: number; unknown: number; cancelled: number; scored: number; unscored: number; accuracy: number | null; latency_p50_ms: number | null; latency_p95_ms: number | null; cost: number | null; cost_is_partial: boolean; cost_recorded: number; latency_distribution: Record<string, number>; failures: Record<string, number>; by_category: Record<string, { scored: number; correct: number }>; by_task: Record<string, { scored: number; correct: number }> }
interface Result { run: EvalRun; attempts: Attempt[]; report: { models: ReportModel[]; confusion: Record<string, number>; scoring: string } }
export function EvaluationLab() {
  const client = useQueryClient();
  const initial = new URLSearchParams(location.search);
  const [page, setPage] = useState(initial.get("models") === "1" ? "models" : ["leaderboard", "benchmark", "agents", "runs", "models"].includes(initial.get("view") || "") ? initial.get("view")! : initial.has("benchmark") || initial.has("benchmark_run") || initial.has("pipeline") ? "benchmark" : initial.has("run") ? "runs" : "benchmark");
  function choosePage(next: string) { setPage(next); const u = new URL(location.href); u.searchParams.set("view", next); u.searchParams.delete("models"); history.replaceState(null, "", u); }

  const [name, setName] = useState("");
  const [releaseId, setReleaseId] = useState("");
  const [modelIds, setModelIds] = useState(["demo"]);
  const [mode, setMode] = useState("text");
  const [category, setCategory] = useState("");
  const [batchId, setBatchId] = useState("");
  const [tags, setTags] = useState("");
  const [taskType, setTaskType] = useState("");
  const [sampleIds, setSampleIds] = useState("");
  const [sampleSize, setSampleSize] = useState("");
  const [seed, setSeed] = useState(42);
  const [concurrency, setConcurrency] = useState(2);
  const [maxCalls, setMaxCalls] = useState(100);
  const [selected, setSelected] = useState(new URLSearchParams(location.search).get("run") || "");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [filter, setFilter] = useState("");
  const [retryIds, setRetryIds] = useState<string[]>([]);
  const [probe, setProbe] = useState<unknown>(null);
  const [probeSample, setProbeSample] = useState("");
  const models = useQuery({ queryKey: ["models"], queryFn: () => api<ModelConfig[]>("/settings/models") });
  const releases = useQuery({ queryKey: ["research", "releases"], queryFn: () => api<Release[]>("/evaluation/releases") });
  const result = useQuery({ queryKey: ["research", "evaluation", selected], queryFn: () => api<Result>("/evaluation/runs/" + selected), enabled: !!selected, refetchInterval: 2000 });
  const jobs = useQuery({ queryKey: ["research", "jobs"], queryFn: () => api<Job[]>("/research/jobs"), refetchInterval: 2500 });
  const samples = useQuery({ queryKey: ["research", "samples"], queryFn: () => api<Sample[]>("/review/samples") });
  const release = releases.data?.find(r => r.id === (releaseId || releases.data?.find(r => r.contract === "research.v2")?.id));
  const refresh = () => client.invalidateQueries({ queryKey: ["research"] });
  async function action(fn: () => Promise<unknown>) {
    setBusy(true); setError("");
    try { await fn(); await refresh(); } catch (e) { setError(String(e)); } finally { setBusy(false); }
  }
  const chosenIds = sampleIds.split(/[\s,]+/).filter(Boolean);
  const chosenTags = tags.split(",").map(s => s.trim()).filter(Boolean);
  let entries = (release?.entries || []).filter(e => (!category || e.revision.content.category === category) && (!batchId || e.batch_id === batchId) && (!chosenIds.length || chosenIds.includes(e.sample_id)) && chosenTags.every(t => e.revision.content.tags.includes(t)));
  const maxEstimate = entries.flatMap(e => e.revision.content.questions).filter(q => !taskType || q.task_type === taskType).length * modelIds.length;
  if (sampleSize) entries = entries.slice(0, Number(sampleSize));
  const attempts = result.data?.attempts || [];
  const shown = attempts.filter(a => !filter || a.status === filter || a.error?.category === filter || filter === "unscored" && a.status === "completed" && a.score == null);
  return <>
    <p className="screenshot-scope-note">评测范围按数据版本与标注等级确定。自动预标注不等同于人工金标；合成数据的通过表示满足审核要求，不表示真实司法证据。</p>
    <div className="research-tabs"><Button aria-current={page === "leaderboard" ? "page" : undefined} onClick={() => choosePage("leaderboard")}>Leaderboard · 排行榜</Button><Button aria-current={page === "agents" ? "page" : undefined} onClick={() => choosePage("agents")}>案件方法与论文实验</Button><Button aria-current={page === "benchmark" ? "page" : undefined} onClick={() => choosePage("benchmark")}>样本完整评测（KIE / VQA）</Button><Button aria-current={page === "runs" ? "page" : undefined} onClick={() => choosePage("runs")}>评测配置与结果</Button><Button aria-current={page === "models" ? "page" : undefined} onClick={() => choosePage("models")}>模型设置</Button></div>
    <ErrorText error={error || releases.error || models.error || result.error || jobs.error || samples.error} />
    {page === "leaderboard" ? <Leaderboard /> : page === "agents" ? <AgentExperiments /> : page === "benchmark" ? <BenchmarkPanel /> : page === "models" ? <><ModelSettings /><Card><h2>研究样本连通性测试</h2><SearchableSelect label={<>图片测试样本</>} value={probeSample} onChange={e => setProbeSample(e.target.value)}><option value="">选择已渲染样本</option>{samples.data?.filter(s => s.published_manifest).map(s => <option key={s.id} value={s.id}>{s.title}</option>)}</SearchableSelect>
      {<Paged items={models.data} label="评测模型" layout="block">{(pageItems) => pageItems.map(m => <div className="toolbar" key={m.id}><strong>{m.name}</strong><Button disabled={busy} onClick={() => action(async () => setProbe(await api("/evaluation/models/" + m.id + "/test", { mode: "text" })))}>测试文本</Button><Button disabled={busy || !probeSample || !m.supports_vision} onClick={() => action(async () => setProbe(await api("/evaluation/models/" + m.id + "/test", { mode: "image", sample_id: probeSample })))}>测试研究图片</Button></div>)}</Paged>}
      {probe != null && <JsonView value={probe} />}
    </Card></> : <>
      <Card><h2>创建评测运行</h2><p>让所选模型回答同一组问题。只有人工确认的标准答案才能用于计分；收到回答不等于答对。</p>{!release && <div className="research-orientation"><strong>先准备审核通过的数据</strong><p>目前没有可用的已发布评测集。请先在审核台完成审核并发布，再回来选择。</p><a href="/review.html?section=imports">前往审核与发布 →</a><p>想查看已经保存的试跑？<a href="/evaluation.html?operations=1">打开流程与结果</a>。</p></div>}
        <form className="research-form" onInvalidCapture={revealInvalidField} onSubmit={e => {
          e.preventDefault(); if (!release) return;
          void action(async () => {
            const run = await api<EvalRun>("/evaluation/runs", { name, release_id: release.id, model_ids: modelIds, mode, category, batch_id: batchId, tags: chosenTags, task_type: taskType, sample_ids: chosenIds, sample_size: sampleSize ? Number(sampleSize) : null, seed, concurrency, max_calls: maxCalls, idempotency_key: key() });
            setSelected(run.id); setName(""); setRetryIds([]);
          });
        }}>
          <div className="research-grid-3"><label>运行名称<Input required value={name} onChange={e => setName(e.target.value)} /></label>
<SearchableSelect label={<>已审核并发布的数据</>} value={release?.id || ""} required onChange={e => { setReleaseId(e.target.value); setCategory(""); setBatchId(""); }}><option value="" disabled>先在审核台发布版本</option>{releases.data?.map(r => <option key={r.id} value={r.id} disabled={r.contract !== "research.v2"}>{r.contract !== "research.v2" ? "历史未绑定 · " : ""}{r.name} · {r.entries.length} 条</option>)}</SearchableSelect>
<label>输入模式<select value={mode} onChange={e => setMode(e.target.value)}><option value="text">只看文字</option><option value="image">只看单张截图</option><option value="multimodal">同时看文字和单张截图</option><option value="multi_image">看多张截图</option></select></label>
<label>最多调用次数<Input type="number" min={1} max={10000} value={maxCalls} onChange={e => setMaxCalls(Number(e.target.value))} /></label></div><p className="research-hint">输入模式决定模型能看到什么；多页截图请选择“看多张截图”。调用次数上限用来避免一次运行过多题目。</p>
          <details><summary>高级设置：只测部分样本与运行速度</summary><div className="research-grid-3"><SearchableSelect label={<>类别</>} value={category} onChange={e => setCategory(e.target.value)}><option value="">全部类别</option>{[...new Set(release?.entries.map(e => e.revision.content.category) || [])].map(c => <option key={c}>{c}</option>)}</SearchableSelect>
<SearchableSelect label={<>生成批次</>} value={batchId} onChange={e => setBatchId(e.target.value)}><option value="">全部批次</option>{[...new Set(release?.entries.map(e => e.batch_id).filter(Boolean) || [])].map(c => <option key={c} value={c!}>{c}</option>)}</SearchableSelect>
<label>任务类型<Input value={taskType} placeholder="留空为全部" onChange={e => setTaskType(e.target.value)} /></label>
<label>标签（逗号分隔，全部匹配）<Input value={tags} onChange={e => setTags(e.target.value)} /></label>
<label>固定种子抽样条数<Input type="number" min={1} max={500} value={sampleSize} placeholder="留空为全选" onChange={e => setSampleSize(e.target.value)} /></label>
<label>Seed<Input type="number" value={seed} onChange={e => setSeed(Number(e.target.value))} /></label>
<label>并发<Input type="number" min={1} max={8} value={concurrency} onChange={e => setConcurrency(Number(e.target.value))} /></label></div>
          <label>显式样本 ID（逗号或换行分隔；留空为范围内全部）<textarea rows={2} value={sampleIds} onChange={e => setSampleIds(e.target.value)} /></label>
          </details><fieldset><legend>勾选评测模型</legend><label className="research-check"><Input type="checkbox" checked={modelIds.includes("demo")} onChange={e => setModelIds(e.target.checked ? [...modelIds, "demo"] : modelIds.filter(id => id !== "demo"))} />离线演练（不调用模型，不计分）</label>
            {<Paged items={models.data} label="评测模型" layout="block">{(pageItems) => pageItems.map(m => <label key={m.id} className="research-check"><Input type="checkbox" checked={modelIds.includes(m.id)} onChange={e => setModelIds(e.target.checked ? [...modelIds, m.id] : modelIds.filter(id => id !== m.id))} />{m.name} · {m.model_name} · {m.supports_vision ? "文本 / 图片" : "文本"}{!m.allow_external_egress && " · 未启用请求"}</label>)}</Paged>}
          </fieldset>
          <p>输出上限与费用单价在模型设置中管理。这次会保存各模型的配置，后续修改不会改变本次记录。</p>
          <p>范围：{entries.length} 条样本 · {modelIds.length} 个模型 · 抽样前最多 {maxEstimate} 次调用。服务器按冻结后的实际题目数校验预算。</p>
          <Button disabled={busy || !release || release.contract !== "research.v2" || !modelIds.length}>开始评测</Button>
        </form>
      </Card>
      {result.data && <>
        <Card><h2>{result.data.run.name} · <Status value={result.data.run.status} /></h2>
          <p>总任务 {result.data.run.tasks.length} · 完成 {attempts.filter(a => a.status === "completed").length} · 失败 {attempts.filter(a => a.status === "failed").length} · 未知 {attempts.filter(a => a.status === "unknown").length} · 取消 {attempts.filter(a => a.status === "cancelled").length} · 并发 {result.data.run.concurrency}</p>
          <a href={"/evaluation.html?audit=1&object=" + encodeURIComponent(result.data.run.id)}>运行操作历史</a>
          <details><summary>这次使用的数据和关联运行</summary><p>数据版本编号：{result.data.run.release_id}</p><p>上次运行编号：{result.data.run.parent_run_id || "无"}</p></details>
          <p>计分只比较回答与人工标准答案是否完全一致，不代表法律判断正确率。没有人工确认的标准答案时，会保留回答并标为未计分。</p>
          <Paged items={result.data.report.models} label="模型评测报告" layout="block">{(visibleRows3) => <><div className="research-table-wrap" tabIndex={0}><table><thead><tr><th>模型</th><th>完成 / 总量</th><th>已评分 / 未评分</th><th>精确匹配率</th><th>典型请求耗时</th><th>估算成本</th></tr></thead><tbody>{visibleRows3.map(g => <tr key={g.model.id}><td>{g.model.name}</td><td>{g.completed} / {g.total}</td><td>{g.scored} / {g.unscored}</td><td>{g.accuracy == null ? "尚未计分" : num(g.accuracy * 100, "%")}{g.scored > 0 && <progress max={1} value={g.accuracy || 0} aria-label={g.model.name + "精确匹配率"} />}</td><td>{num(g.latency_p50_ms == null ? null : g.latency_p50_ms / 1000)} 秒</td><td>{num(g.cost)} {g.model.billing?.currency}<br /><small>{g.cost_is_partial ? "部分费用未知；仅列已知部分" : "已记录费用"} · {g.cost_recorded}项</small></td></tr>)}</tbody></table></div></>}</Paged>
          {<Paged items={result.data.report.models} label="模型评测报告" layout="block">{(pageItems) => pageItems.map(g => <details key={g.model.id}><summary>{g.model.name} · 按任务 / 类别指标与失败分布</summary><div className="research-two-column"><div><h3>请求耗时分布</h3><p>典型耗时为中位数，即一半请求不超过这个用时。较慢请求耗时（95%请求不超过）：{num(g.latency_p95_ms == null ? null : g.latency_p95_ms / 1000)} 秒。</p>{Object.entries(g.latency_distribution || {}).map(([name, count]) => <div key={name}>{name} · {count}<progress aria-label={name + "延迟区间"} max={g.total} value={count} /></div>)}</div><div><h3>失败分布</h3>{Object.entries(g.failures).map(([name, count]) => <div key={name}>{name} · {count}<progress aria-label={name + "失败数量"} max={g.total} value={count} /></div>)}</div></div><Paged items={Object.entries(g.by_category)} label="分类指标" layout="block">{(visibleRows4) => <><Paged items={Object.entries(g.by_task)} label="任务指标" layout="block">{(visibleRows5) => <><div className="research-table-wrap" tabIndex={0}><table><thead><tr><th>分组</th><th>已评分</th><th>精确匹配率</th></tr></thead><tbody>{visibleRows4.map(([name, v]) => <tr key={"category:" + name}><td>类别 · {name}</td><td>{v.scored}</td><td>{num(v.correct / v.scored * 100, "%")}</td></tr>)}{visibleRows5.map(([name, v]) => <tr key={"task:" + name}><td>任务 · {name}</td><td>{v.scored}</td><td>{num(v.correct / v.scored * 100, "%")}</td></tr>)}</tbody></table></div></>}</Paged></>}</Paged><JsonView value={{ endpoint: g.model.endpoint, model: g.model.model }} /></details>)}</Paged>}
          <details><summary>分类混淆矩阵（存在有效分类金标时）</summary>{Object.keys(result.data.report.confusion).length ? <Paged items={Object.entries(result.data.report.confusion)} label="分类混淆矩阵" layout="block">{(visibleRows6) => <><div className="research-table-wrap" tabIndex={0}><table><thead><tr><th>金标 → 预测</th><th>数量</th></tr></thead><tbody>{visibleRows6.map(([k, n]) => <tr key={k}><td>{k}</td><td>{n}</td></tr>)}</tbody></table></div></>}</Paged> : <p>当前没有可计算的分类结果。</p>}</details>
          <div className="toolbar"><a href={"/v1/evaluation/runs/" + selected + "/export"}>导出全部结果与快照</a><a href={"/v1/evaluation/runs/" + selected + "/export?failures_only=true"}>导出失败 / 未知项</a>
            <Button disabled={busy || !["failed", "unknown", "cancelled"].some(status => attempts.some(a => a.status === status))} onClick={() => action(async () => { const retry = await api<EvalRun>("/evaluation/runs/" + selected + "/retry", { task_ids: retryIds, idempotency_key: key() }); setSelected(retry.id); setRetryIds([]); })}>按所选失败项创建重试（未选则全部失败项）</Button>
          </div>
        </Card>
        <Card><h2>逐题结果与错误</h2><SearchableSelect label={<>筛选</>} value={filter} onChange={e => setFilter(e.target.value)}><option value="">全部</option>{["completed", "failed", "unknown", "cancelled", "unscored", ...new Set(attempts.flatMap(a => a.error ? [a.error.category] : []))].map(c => <option key={c}>{c}</option>)}</SearchableSelect>
          {<Paged items={shown} label="逐题结果" layout="block" resetKey={selected + filter}>{(pageItems) => pageItems.map(a => { const task = result.data!.run.tasks.find(t => t.id === a.task_id); return <details key={a.id}><summary><Status value={a.status} /> {task?.model.name} · {task?.question_id} · {term(a.scoring_status)} · {num(a.score)}</summary>
            {["failed", "unknown", "cancelled"].includes(a.status) && <label className="research-check"><Input type="checkbox" checked={retryIds.includes(a.task_id)} onChange={e => setRetryIds(e.target.checked ? [...retryIds, a.task_id] : retryIds.filter(id => id !== a.task_id))} />选入重试范围</label>}
            <p>耗时：{num(a.latency_ms == null ? null : a.latency_ms / 1000)} 秒</p>
            {a.error && <FailureNotice error={a.error} />}
            <pre className="research-markdown">{a.answer}</pre><a href={"/review.html?sample=" + task?.sample_id}>查看来源与质量记录</a>
            <details><summary>技术记录：调用编号与原始返回</summary><JsonView value={a} /></details>
          </details>; })}</Paged>}
          {!shown.length && <p>没有匹配的结果；运行中会逐项更新。</p>}
        </Card>
      </>}
      <JobsPanel jobs={(jobs.data || []).filter(j => j.kind === "evaluation" && (!selected || j.payload.run_id === selected))} refresh={refresh} />
    </>}
    {page === "benchmark" ? <details><summary>全部运行历史（含旧试跑）</summary><EvaluationHistory selected={selected} select={id => { setSelected(id); setRetryIds([]); choosePage("runs"); }} /></details> : page === "runs" && <EvaluationHistory selected={selected} select={id => { setSelected(id); setRetryIds([]); choosePage("runs"); }} />}
  </>;
}
