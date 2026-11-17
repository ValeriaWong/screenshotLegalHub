import { SearchableSelect } from "../../components/collections";
import { Paged } from "../../components/collections";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Button, Card, Input } from "../../components/ui";
import { api, stamp } from "./client";
import { kindName, term, flowDecision } from "./presentation";
import { ErrorText, JsonView, Status, FailureNotice } from "./shared";
interface Item { id: string; kind: string; title: string; status: string; created_at: string; href: string; mode?: string; scope?: string }
interface Detail { id: string; kind: string; body: Record<string, any>; related: { label: string; id: string; href: string }[]; href: string }
export function ObjectLink({ id, label = "打开相关页面" }: { id: string; label?: string }) {
  const target = useQuery({ queryKey: ["research", "resolve", id], queryFn: () => api<{ href: string }>("/research/resolve?object_id=" + encodeURIComponent(id)), enabled: !!id, retry: false });
  return target.data ? <a href={target.data.href}>{label} →</a> : target.error ? <span>对象不存在或无访问权限</span> : <span>解析对象…</span>;
}
export function OperationsPanel() {
  const initial = new URLSearchParams(location.search);
  const [kind, setKind] = useState(initial.get("kind") || ""), [selected, setSelected] = useState(initial.get("record") || "");
  const [selectedKind, setSelectedKind] = useState(kind), [q, setQ] = useState(""), [search, setSearch] = useState(""), [offsets, setOffsets] = useState([0]);
  const query = new URLSearchParams({ kind, q: search, offset: String(offsets.at(-1)) });
  const rows = useQuery({ queryKey: ["research", "operations", query.toString()], queryFn: () => api<{ items: Item[]; total: number; kinds: string[]; next_offset: number | null }>("/research/operations?" + query), refetchInterval: 5000 });
  const flows = useQuery({ queryKey: ["research", "flows"], queryFn: () => api<{ items: Item[] }>("/research/operations?kind=research.flow&limit=50"), refetchInterval: 5000 });
  const detail = useQuery({ queryKey: ["research", "operation", selectedKind, selected], queryFn: () => api<Detail>("/research/operations/" + encodeURIComponent(selectedKind) + "/" + encodeURIComponent(selected)), enabled: !!selected && !!selectedKind, refetchInterval: 5000 });
  function choose(item: Item) { setSelected(item.id); setSelectedKind(item.kind); const u = new URL(location.href); u.searchParams.set("record", item.id); u.searchParams.set("kind", item.kind); history.replaceState(null, "", u); }
  const b = detail.data?.body;
  const migration = b?.summary?.flow_type === "data_migration";
  const software = b?.summary?.flow_type === "software_verification";
  const pipeline = selectedKind === "benchmark.pipeline";
  const decision = pipeline && b ? { title: ["queued", "running"].includes(b.status) ? "按图评测正在执行" : "按图评测已结束，请核对未完成项", meaning: "区域题使用参考区域引导的预测消息，整图题独立执行；收到回答不代表答对。", next: "打开按图流程查看每张图、失败原因和固定评分版本；恢复或重试请从该流程操作。" } : migration ? { title: "旧工作流已接入，参考答案待审核", meaning: "原图、标注、历史响应和 IoU 回放已保留。本轮没有调用收费模型，也没有自动认证金标。", next: "打开 KIE / VQA 标注，核对图片身份、目标答案与案件组，再发布人工确认的任务。" } : software ? { title: "软件验证已完成", meaning: "本轮展示本地回归和模拟服务的测试结果。真实模型调用 " + b?.summary.real_model_calls + " 次；不产生新的模型质量结论。", next: b?.summary.next_action || "复核历史质量意见，需要升级旧图时在审核台显式生成新版本，再重新审核。" } : b?.summary ? flowDecision(b.status, b.summary) : null;
  const title = (i: Item) => i.title === i.kind || i.title.includes(".") && i.title === i.scope ? kindName(i.kind) : term(i.title);
  return <>
    <Card><h2>流程与结果</h2><p>选择一轮工作，先看实际进度和下一步。需要追查单次修改或调用时，再展开下面的记录。</p>
      <div className="toolbar">{<Paged items={flows.data?.items} label="完整流程记录" layout="block">{(pageItems) => pageItems.map(flow => <Button key={flow.id} onClick={() => choose(flow)}>完整流程：{flow.title}</Button>)}</Paged>}</div>
      {!flows.isPending && !flows.data?.items.length && <p>还没有整轮流程记录。你可以先从<a href="/review.html">审核已有样本</a>开始，也可以在下方查找单条记录。</p>}<ErrorText error={flows.error} />
    </Card>
    {!!selected && <Card><h2>过程与结果详情</h2><p>{kindName(selectedKind)}{b?.name ? " · " + b.name : ""}</p><ErrorText error={detail.error} />{detail.isPending && <p>正在读取…</p>}{b && <>
      {decision && <section className="research-orientation" aria-label="本轮结论与下一步"><h3>{decision.title}</h3><p>{decision.meaning}</p><p><strong>下一步：</strong>{decision.next}</p>
        {b.status === "awaiting_human_review" && b.sample_ids?.[0] && <a className="research-link-button research-primary-action" href={"/review.html?sample=" + encodeURIComponent(b.sample_ids[0])}>打开待审样本</a>}
        {b.summary?.formal_releases > 0 && <a href="/evaluation.html?view=runs">查看正式评测 →</a>}
      </section>}
      {pipeline && <><div className="research-stat-cards" aria-label="按图流程进度"><div><strong>{b.images}</strong>逻辑图片</div><div><strong>{b.planned_units}</strong>计划执行单元（失败仍保留）</div><div><strong>{b.reserved_calls} / {b.max_calls}</strong>调用额度已占用 / 上限</div></div><p>{Object.entries(b.execution_counts || {}).map(([s,n]) => term(s) + " " + n).join("；") || "计划已保存，等待开始"}</p>{b.stop_reason && <p>停止原因：{b.stop_reason}</p>}<a href={"/evaluation.html?benchmark=1&pipeline=" + selected}>查看按图完整结果与恢复操作 →</a></>}
      {migration && <><div className="research-stat-cards"><div><strong>{b.summary.counts.images}</strong>逻辑图片</div><div><strong>{b.summary.counts.tasks}</strong>已接入任务</div><div><strong>{b.summary.counts.legacy_iou}</strong>精确回放旧 IoU</div></div><a href={"/review.html?section=benchmark&benchmark=" + b.summary.dataset_id}>开始核对 KIE / VQA 标注 →</a><a href="/evaluation.html?benchmark=1">查看任务评测与回放 →</a></>}
      {software && <div className="research-stat-cards" aria-label="本轮软件验证"><div><strong>{b.summary.verification.backend}</strong>后端回归通过</div><div><strong>{b.summary.verification.frontend_unit}</strong>前端单元测试通过</div><div><strong>{b.summary.verification.browser}</strong>浏览器场景通过</div></div>}
      {b.summary && !software && !migration && <><div className="research-stat-cards" aria-label="本轮关键进度"><div><strong>{b.summary.generated_candidates ?? "—"}</strong>生成的待审核样本</div><div><strong>{b.summary.qa_success ?? "—"} / {b.summary.qa_requests ?? "—"}</strong>成功返回的试跑请求<p className="research-hint">表示收到了回答，尚不能说明答对。</p></div><div><strong>{b.summary.formal_releases ?? "—"}</strong>已发布的数据版本</div></div>
        {b.summary.usage_missing_requests > 0 && <p>费用记录不完整：{b.summary.usage_missing_requests} 次调用缺少用量，暂时无法核对完整费用。</p>}</>}
      {b.historical_sync && <p className="research-hint" role="status">历史试跑同步 · 同步时间 {stamp(b.synced_at)}；这里展示保存的实际结果。</p>}
      {Array.isArray(b.steps) && <><h3>各步骤做到哪里</h3><ol>{<Paged<any> items={b.steps} label="流程步骤" layout="list">{(pageItems, pageOffset) => pageItems.map((s: any, pageIndex) => { const i = pageIndex + pageOffset; return (<li key={i}><strong>{s.stage}</strong>：{s.result}</li>); })}</Paged>}</ol></>}
      {b.phase && <p>正在做：{term(b.phase)} · <Status value={b.status} /></p>}{b.error && <FailureNotice error={b.error} />}
      {b.scope && <p>{term(b.scope)} · {term(b.mode)} · {b.success ? "已收到模型回答" : "未收到有效回答"} · 未计分</p>}
      {b.input?.question && <><h3>交给模型的问题</h3><p>{b.input.question}</p></>}
      {b.response?.raw && <><h3>模型返回</h3><p className="research-hint">以下为模型原始回答，请结合来源材料判断是否可靠。</p><pre className="research-markdown">{b.response.raw}</pre><p>耗时：{b.response.latency_ms == null ? "未记录" : (b.response.latency_ms / 1000).toFixed(1) + " 秒"} · 估算费用：{b.response.cost_estimate ?? "未知"} {b.response.cost_currency || ""}</p></>}
      {b.markdown && <><h3>使用的规则</h3><pre className="research-markdown">{b.markdown}</pre><p>本次修改原因：{b.note || "未记录"}</p></>}
      {b.findings && <><h3>评估发现</h3><pre className="research-markdown">{b.findings}</pre><h3>修改建议</h3><pre className="research-markdown">{b.suggestions}</pre><p>{term(b.method)} · {term(b.coverage || b.review_scope)} · <Status value={b.verdict} /> · 参考分数：{b.score ?? "未评分"}</p></>}
      <div className="toolbar"><ObjectLink id={selected} /><a href={"/review.html?audit=1&object=" + encodeURIComponent(selected)}>查看这项工作的操作历史</a>{b.flow_id && <a href={"/review.html?audit=1&correlation_id=" + encodeURIComponent(b.flow_id)}>查看整轮操作历史</a>}</div>
      {!!detail.data?.related.length && <details><summary>打开相关样本与记录</summary><ul>{<Paged items={detail.data.related} label="关联工作记录" layout="list">{(pageItems, pageOffset) => pageItems.map((r, pageIndex) => { const i = pageIndex + pageOffset; return (<li key={r.id + i}><a href={r.href}>{({sample_id:"来源样本",batch_id:"生成批次",run_id:"评测运行",job_id:"后台任务",parent_job_id:"上一次任务",prompt_id:"使用的规则",release_id:"已发布评测集"} as Record<string,string>)[r.label] || r.label} →</a></li>); })}</Paged>}</ul></details>}
      {b.artifacts && <details><summary>下载本轮说明、样本和完整记录（{b.artifacts.length} 份）</summary><ul>{<Paged<any> items={b.artifacts} label="可下载产物" layout="list">{(pageItems, pageOffset) => pageItems.map((a: any, pageIndex) => { const i = pageIndex + pageOffset; return (<li key={a.name}><a href={"/v1/research/flows/" + encodeURIComponent(selected) + "/artifacts/" + encodeURIComponent(a.name)}>{({"REPORT.md":"本轮运行说明","RESULTS.html":"逐样本图文回答对照","studio-prompt-history.md":"生成规则修改历史","review-prompt-history.md":"评估规则修改历史","qa-results.json":"完整问答记录","quality-records.json":"完整质量意见"} as Record<string,string>)[a.name] || (a.name.endsWith(".zip") ? "候选样本包 " + (i + 1) : a.name)}</a></li>); })}</Paged>}</ul></details>}
      {b.linked_records && <details><summary>查看各步骤的详细结果（显示 {b.linked_records.length} / {b.linked_records_total || b.linked_records.length} 条）</summary><Paged<Item> items={b.linked_records} label="步骤详细结果" layout="block">{(visibleRows2) => <><div className="research-table-wrap" tabIndex={0}><table><thead><tr><th>这是什么</th><th>内容</th><th>执行状态</th><th>详情</th></tr></thead><tbody>{visibleRows2.map((i: Item) => <tr key={i.kind + i.id}><td>{kindName(i.kind)}</td><td>{title(i)}</td><td><Status value={i.status} /></td><td><a href={i.href}>打开步骤与结果 →</a></td></tr>)}</tbody></table></div></>}</Paged></details>}
      <details><summary>技术详情：编号、用量与完整记录</summary><p>用于排查问题和复现结果，日常审核通常不需要填写或理解。</p><p>记录编号：{selected}</p>{b.request_ledger && <details><summary>逐次调用用量与失败记录（{b.request_ledger.length}）</summary><JsonView value={b.request_ledger} /></details>}<JsonView value={b} /></details>
    </>}</Card>}
    <Card><details><summary>查找单条操作记录（共 {rows.data?.total ?? "—"} 条）</summary>
      <form className="toolbar" onSubmit={e => { e.preventDefault(); setSearch(q); setOffsets([0]); }}><SearchableSelect label={<>记录类型</>} value={kind} onChange={e => { setKind(e.target.value); setOffsets([0]); }}><option value="">全部类型</option>{rows.data?.kinds.map(k => <option key={k} value={k}>{kindName(k)}</option>)}</SearchableSelect><label>记录关键词<Input value={q} onChange={e => setQ(e.target.value)} /></label><Button>检索记录</Button><a href="/review.html?audit=1">打开操作日志</a></form>
      <ErrorText error={rows.error} /><div className="research-table-wrap" tabIndex={0}><table><thead><tr><th>时间</th><th>记录类型 / 状态</th><th>内容</th><th>详情</th></tr></thead><tbody>{rows.data?.items.map(i => <tr key={i.kind + i.id}><td>{i.created_at && stamp(i.created_at)}</td><td>{kindName(i.kind)}<br /><Status value={i.status} /> {term(i.mode)}</td><td>{title(i)}</td><td><Button onClick={() => choose(i)}>查看过程与结果</Button></td></tr>)}</tbody></table></div>
      <div className="toolbar"><Button disabled={offsets.length === 1} onClick={() => setOffsets(v => v.slice(0, -1))}>上一页</Button><Button disabled={rows.data?.next_offset == null} onClick={() => setOffsets(v => [...v, rows.data!.next_offset!])}>下一页</Button></div>
    </details></Card>
  </>;
}
