import { SearchableSelect } from "../../components/collections";
import { Paged } from "../../components/collections";
import { BenchmarkFeedback } from "./BenchmarkFeedback";
import { RegenerationPackagePanel } from "./RegenerationPackagePanel";
import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, Card, Input } from "../../components/ui";
import type { ModelConfig } from "../../api/client";
import { api, key, num, defaultRender, type Sample, type Prompt, type Batch, type Comparison, type Job, type ReviewComment } from "./client";
import { revealInvalidField, ErrorText, JobsPanel, JsonView, PromptEditor, Status } from "./shared";
export function DataStudio() {
  const client = useQueryClient();
  const [page, setPage] = useState("batches");
  const [name, setName] = useState("");
  const [dataset, setDataset] = useState("studio-candidates");
  const [sourceId, setSourceId] = useState("");
  const [promptId, setPromptId] = useState("");
  const [modelId, setModelId] = useState("demo");
  const [count, setCount] = useState(1);
  const [language, setLanguage] = useState("");
  const [platform, setPlatform] = useState("");
  const [taskType, setTaskType] = useState("qa");
  const [constraints, setConstraints] = useState("");
  const [useFeedback, setUseFeedback] = useState(true);
  const [excludedFeedback, setExcludedFeedback] = useState<string[]>([]);
  const [seed, setSeed] = useState(42);
  const [render, setRender] = useState(defaultRender);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const sources = useQuery({ queryKey: ["research", "sources"], queryFn: () => api<Sample[]>("/studio/sources") });
  const prompts = useQuery({ queryKey: ["research", "studio", "prompts"], queryFn: () => api<Prompt[]>("/studio/prompts") });
  const models = useQuery({ queryKey: ["models"], queryFn: () => api<ModelConfig[]>("/settings/models") });
  const batches = useQuery({ queryKey: ["research", "batches"], queryFn: () => api<Batch[]>("/studio/batches"), refetchInterval: 2500 });
  useEffect(() => { const target = new URLSearchParams(location.search).get("batch"); if (target && batches.data?.some(b => b.id === target)) document.getElementById("batch-" + target)?.scrollIntoView({ block: "start" }); }, [batches.data]);
  const comparison = useQuery({ queryKey: ["research", "comparison"], queryFn: () => api<Comparison[]>("/studio/comparison"), refetchInterval: 5000 });
  const jobs = useQuery({ queryKey: ["research", "jobs"], queryFn: () => api<Job[]>("/research/jobs"), refetchInterval: 2500 });
  const source = sources.data?.find(s => s.id === (sourceId || sources.data[0]?.id));
  const feedback = useQuery({ queryKey: ["research", "feedback", source?.id], queryFn: () => api<ReviewComment[]>("/studio/feedback?source_sample_id=" + encodeURIComponent(source!.id)), enabled: !!source, refetchInterval: 5000 });
  const prompt = prompts.data?.find(p => p.id === (promptId || prompts.data[0]?.id));
  const refresh = () => client.invalidateQueries({ queryKey: ["research"] });
  return <>
    <p className="screenshot-scope-note">所有生成产物均为合成数据。审核分别核对原文支持、合理模拟和无依据事实；对话自然不代表事实正确。</p>
    <div className="research-tabs">{[["batches", "生成批次"], ["regen", "从 B 修正包重生成"], ["prompts", "生成规则与修改历史"], ["comparison", "质量结果对比"]].map(([id, name]) => <Button key={id} aria-current={page === id ? "page" : undefined} onClick={() => setPage(id)}>{name}</Button>)}</div>
    <ErrorText error={error || sources.error || prompts.error || batches.error || models.error || comparison.error || jobs.error} />
    {page === "regen" ? <RegenerationPackagePanel /> : page === "prompts" ? <PromptEditor purpose="studio" /> : page === "comparison" ? <Card>
      <h2>比较各批次的审核意见</h2>
      <p>这里汇总审核台的意见。请先看哪些样本仍需修改；模型分数仅供参考。只有相同样本、相同评估规则的结果才适合比较。</p>
      <p className="research-hint">同一批次可能有多行，因为检查方法不同。分数缺失表示未评分；人工意见和模型参考分分别展示。</p><Paged items={comparison.data} label="质量结果对比" layout="block" searchText={c => [(batches.data || []).find(b => b.id === c.batch_id)?.name, (prompts.data || []).find(p => p.id === c.prompt_id)?.name, c.stage, c.protocol_id].join(" ")}>{(visibleRows7) => <><div className="research-table-wrap" tabIndex={0}><table><thead><tr><th>批次 / 生成规则</th><th>检查阶段 / 方法</th><th>已检查比例 / 尝试次数</th><th>样本</th><th>人工已审</th><th>人工均分</th><th>模型参考均分</th><th>人工通过率</th><th>修订次数</th></tr></thead><tbody>
        {visibleRows7.map(c => <tr key={[c.batch_id, c.prompt_id, c.stage, c.protocol_id].join(":")}><td>{batches.data?.find(b => b.id === c.batch_id)?.name || (c.batch_id === "imported" ? "已有来源样本" : "其他批次")}<br /><small>{prompts.data?.find(p => p.id === c.prompt_id) ? prompts.data.find(p => p.id === c.prompt_id)!.name + " · v" + prompts.data.find(p => p.id === c.prompt_id)!.version : "未使用生成规则"}</small></td>
          <td>{c.stage === "initial" ? "生成初稿" : "修改稿"}<br /><details><summary>评估方法与版本</summary><p>参考编号：{c.protocol_id}</p><JsonView value={c.protocol} /></details></td><td>{num((c.coverage || 0) * 100, "%")}<br />{c.samples}/{c.cohort_total}<br /><small>任务 {c.quality_attempts || 0} · 失败/取消 {c.failed_attempts || 0} · 未知 {c.unknown_attempts || 0}</small></td><td>{c.samples}</td><td>{c.reviewed_samples}</td><td>{num(c.human_mean)} ({c.human_scored})</td><td>{num(c.model_mean)} ({c.model_scored})</td><td>{num(c.human_pass_rate == null ? null : c.human_pass_rate * 100, "%")}</td><td>{c.corrections}</td></tr>)}
      </tbody></table></div></>}</Paged>
      {!comparison.data?.length && <p>生成或导入样本并完成质量评估后，这里会出现对比结果。</p>}
      <p><a href="/review.html">前往审核台处理质量意见与评估规则 →</a></p>
      <details><summary>对比所引用的质量记录 ID</summary><JsonView value={comparison.data} /></details>
    </Card> : <>
      <Card><h2>新建生成批次</h2><p>选择一份来源和一套生成规则，制作新的待审样本。生成完成后请到审核台核对。</p><ol className="research-steps"><li>选来源和规则</li><li>说明本次要求</li><li>生成后送审核</li></ol>{!source && <p role="status">还没有来源样本。请先<a href="/review.html">导入或创建样本</a>。</p>}{!prompt && <p role="status">还没有生成规则。<Button type="button" onClick={() => setPage("prompts")}>先创建生成规则</Button></p>}
        <form className="research-form" onInvalidCapture={revealInvalidField} onSubmit={e => {
          e.preventDefault(); if (!source || !prompt) return; setBusy(true); setError("");
          void api("/studio/batches", { name, dataset, source_sample_id: source.id, source_revision: source.revision, prompt_id: prompt.id, model_id: modelId, count, language: language || source.language || "zh", platform: platform || source.platform || "generic", task_type: taskType, constraints, seed, use_review_feedback: useFeedback, feedback_ids: useFeedback ? (feedback.data || []).filter(c => !excludedFeedback.includes(c.id)).map(c => c.id) : [], template: "chat.v1", render, idempotency_key: key() })
            .then(async () => { setName(""); await refresh(); }).catch(e => setError(String(e))).finally(() => setBusy(false));
        }}>
          <div className="research-grid-3"><label>批次名称<Input required value={name} onChange={e => setName(e.target.value)} /></label>
<SearchableSelect label={<>来源样本</>} required value={source?.id || ""} onChange={e => { setSourceId(e.target.value); setExcludedFeedback([]); }}><option value="" disabled>先在审核台导入来源</option>{sources.data?.map(s => <option key={s.id} value={s.id}>{s.title} · r{s.revision}</option>)}</SearchableSelect>
<SearchableSelect label={<>生成规则</>} required value={prompt?.id || ""} onChange={e => setPromptId(e.target.value)}><option value="" disabled>先保存生成规则</option>{prompts.data?.map(p => <option key={p.id} value={p.id}>{p.name} · v{p.version}</option>)}</SearchableSelect>
<SearchableSelect label={<>生成模型</>} value={modelId} onChange={e => setModelId(e.target.value)}><option value="demo">离线演练（只复制来源，不调用模型）</option>{models.data?.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}</SearchableSelect>
<label>数量<Input type="number" min={1} max={50} value={count} onChange={e => setCount(Number(e.target.value))} /></label></div>
          <details><summary>高级设置：归档、语言与生成方式（通常无需更改）</summary><p className="research-hint">语言和平台留空时沿用来源；Seed 只记录抽样设置，不保证模型每次输出相同。</p><div className="research-grid-3"><label>目标数据集<Input required value={dataset} onChange={e => setDataset(e.target.value)} /></label>
<label>语言<Input value={language} onChange={e => setLanguage(e.target.value)} /></label>
<label>平台<Input value={platform} onChange={e => setPlatform(e.target.value)} /></label>
<label>任务类型<Input value={taskType} onChange={e => setTaskType(e.target.value)} /></label>
<label>Seed<Input type="number" value={seed} onChange={e => setSeed(Number(e.target.value))} /></label></div></details>
          <label className="research-check"><Input type="checkbox" checked={useFeedback} onChange={e => setUseFeedback(e.target.checked)} />采用已有审核意见（{feedback.data?.length || 0} 条）</label>
          {!!feedback.data?.length && <details><summary>将使用的审核反馈</summary>{<Paged items={feedback.data} label="生成采用的审核意见" layout="block">{(pageItems) => pageItems.map(c => <p key={c.id}><label className="research-check"><Input type="checkbox" checked={!excludedFeedback.includes(c.id)} onChange={e => setExcludedFeedback(previous => e.target.checked ? previous.filter(id => id !== c.id) : [...previous, c.id])} />r{c.revision} · {c.message_id || "整条样本"} · {c.applicability === "source" ? "长期规则" : "此版本"}：{c.body}</label></p>)}</Paged>}</details>}
          <ErrorText error={feedback.error} />
          <label>本次希望生成什么<textarea rows={4} placeholder="例如：保留金额和人物关系；让对话更自然；不要添加来源未提及的事实。" value={constraints} onChange={e => setConstraints(e.target.value)} /></label>
          <details><summary>高级设置：截图尺寸与排版</summary><div className="research-grid-3">{(["width", "page_height", "font_size"] as const).map(k => <label key={k}>{({width:"图片宽度",page_height:"每页高度",font_size:"文字大小"})[k]}<Input type="number" value={render[k]} onChange={e => setRender({ ...render, [k]: Number(e.target.value) })} /></label>)}</div></details>
          <Button disabled={busy || !source || !prompt || (useFeedback && (feedback.isPending || !!feedback.error))}>开始生成待审样本</Button>
        </form>
      </Card>
      <Card><h2>批次与候选产物</h2>{!batches.data?.length && <p>尚无生成批次。</p>}
        {<Paged items={batches.data} label="生成批次" layout="block" resetKey={new URLSearchParams(location.search).get('batch') || ''} anchorIndex={(batches.data || []).findIndex(b => b.id === new URLSearchParams(location.search).get('batch'))} pageSize={10}>{(pageItems) => pageItems.map(b => <details key={b.id} id={"batch-" + b.id} open={(batches.data?.length || 0) <= 10 || b.id === new URLSearchParams(location.search).get("batch")}><summary><Status value={b.status} /> {b.name} · {b.sample_ids.length}/{b.count} 条候选</summary>
          <a href={"/studio.html?audit=1&object=" + encodeURIComponent(b.id)}>批次操作历史</a><p>模型：{b.model.name} · 生成规则：{b.prompt.name}（第 {b.prompt.version} 版） · 使用来源第 {b.source.number} 版</p>
          <div className="research-stages"><span>生成 {b.sample_ids.length}/{b.count}</span><span>结构校验 {b.sample_ids.length}</span><span>渲染完成 {b.render_statuses.filter(s => s === "completed").length}/{b.count}</span><span>{b.package_ready ? "产物可打包" : "等待产物"}</span></div>
          {b.error && <p role="alert">{b.error.message}</p>}
          <div className="toolbar">{b.package_ready && <a className="research-link-button" href={"/v1/studio/batches/" + b.id + "/export"}>下载样本和完整记录</a>}<Button onClick={() => setPage("comparison")}>查看质量对比</Button></div>
          <ul>{<Paged items={b.sample_ids} label="批次候选样本" layout="list">{(pageItems) => pageItems.map(id => <li key={id}><a href={"/review.html?sample=" + encodeURIComponent(id)}>{sources.data?.find(s => s.id === id)?.title || id} → 审核与纠正</a></li>)}</Paged>}</ul>
          <details><summary>生成设置快照</summary><JsonView value={b} /></details>
        </details>)}</Paged>}
      </Card>
      <JobsPanel jobs={(jobs.data || []).filter(j => j.kind === "generate" || j.kind === "render" && batches.data?.some(b => b.sample_ids.includes(j.payload.sample_id)))} refresh={refresh} />
    </>}
  <BenchmarkFeedback />
</>;
}
