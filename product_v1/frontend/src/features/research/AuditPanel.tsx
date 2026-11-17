import { SearchableSelect } from "../../components/collections";
import { Paged } from "../../components/collections";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Button, Card, Input } from "../../components/ui";
import { api, stamp } from "./client";
import { actionName, kindName, term } from "./presentation";
import { ObjectLink } from "./OperationsPanel";
import { ErrorText, JsonView } from "./shared";
import { FocusDialog } from "./ReviewCanvas";
interface AuditEvent { id: string; seq: number; actor_id: string; actor_type: string; product: string; action: string; object_type: string; object_id: string; outcome: string; occurred_at: string; reason: string; request_id?: string; correlation_id?: string; parent_event_id?: string; context: Record<string, unknown>; changes: Record<string, unknown>; result_ref?: string; formatted_log: string; level: string }
interface Filters { product: string; action: string; outcome: string; object_id: string; actor_id: string; since: string; until: string; q: string; correlation_id: string; request_id: string }
export function AuditPanel({ product }: { product: string }) {
  const url = new URLSearchParams(location.search);
  const objectId = url.get("object") || "";
  const [draft, setDraft] = useState<Filters>({ product: objectId ? "" : new URLSearchParams(location.search).get("audit_product") || "", action: "", outcome: "", object_id: objectId, actor_id: "", since: "", until: "", q: url.get("q") || "", correlation_id: url.get("correlation_id") || "", request_id: url.get("request_id") || "" });
  const [filter, setFilter] = useState(draft), [cursors, setCursors] = useState<(number | null)[]>([null]);
  const [selected, setSelected] = useState(url.get("event") || "");
  const [groupBy, setGroupBy] = useState("day");
  const [mode, setMode] = useState("table");
  const params = new URLSearchParams(Object.entries(filter).filter(([,v]) => v));
  for (const field of ["since", "until"] as const) if (filter[field]) params.set(field, new Date(filter[field] + "+08:00").toISOString());
  const base = params.toString(); const cursor = cursors.at(-1);
  if (cursor) params.set("cursor", String(cursor));
  const events = useQuery({ queryKey: ["research", "audit", base, cursor], queryFn: () => api<{ items: AuditEvent[]; next_cursor: number | null }>("/research/audit-events?" + params.toString()) });
  const summary = useQuery({ queryKey: ["research", "audit-summary", base, groupBy], queryFn: () => api<{ total: number; outcomes: Record<string, number>; actions: Record<string, number>; days: Record<string, number>; groups: Record<string, number> }>("/research/audit-summary?" + base + "&group_by=" + groupBy) });
  const detail = useQuery({ queryKey: ["research", "audit-event", selected], queryFn: () => api<AuditEvent>("/research/audit-events/" + selected), enabled: !!selected });
  const outcomes: Record<string,string> = { success: "成功", rejected: "拒绝/冲突", failed: "失败", unknown: "结果未知" };
  const products: Record<string,string> = { review: "数据审核台", studio: "合成生成台", evaluation: "评测台", workbench: "用户工作台", settings: "模型配置" };
  function object(id: string) { const next = { ...filter, object_id: id, product: "", q: "", action: "", outcome: "", actor_id: "", correlation_id: "", request_id: "", since: "", until: "" }; setFilter(next); setDraft(next); setCursors([null]); }
  return <>
    <Card><h2>操作审计</h2><a href={"/" + product + ".html?operations=1"}>打开流程与结果 →</a><p>输入你想找的内容，再选时间范围。这里记录谁做了什么、是否完成；所有日期按新加坡时间处理。</p>
      <form className="research-form" onSubmit={e => { e.preventDefault(); setFilter(draft); setCursors([null]); }}><div className="research-grid-3">
        <label>日志关键词<Input maxLength={500} value={draft.q} placeholder="多个关键词以空格分隔，全部匹配" onChange={e => setDraft({ ...draft, q: e.target.value })} /></label>
        <SearchableSelect label={<>审计产品</>} value={draft.product} onChange={e => setDraft({ ...draft, product: e.target.value })}><option value="">全部产品</option>{Object.entries(products).map(([k,v]) => <option key={k} value={k}>{v}</option>)}</SearchableSelect>        <SearchableSelect label={<>结果筛选</>} value={draft.outcome} onChange={e => setDraft({ ...draft, outcome: e.target.value })}><option value="">全部结果</option>{Object.entries(outcomes).map(([k,v]) => <option key={k} value={k}>{v}</option>)}</SearchableSelect>        <label>开始时间<Input type="datetime-local" value={draft.since} onChange={e => setDraft({ ...draft, since: e.target.value })} /></label>
        <label>结束时间<Input type="datetime-local" value={draft.until} onChange={e => setDraft({ ...draft, until: e.target.value })} /></label>
      </div><details><summary>更多条件：操作编号、人员与系统动作</summary><p className="research-hint">通常使用关键词和日期即可；这些编号用于定位某一轮工作或排查问题。</p><div className="research-grid-3">        <label>流程 / 关联 ID<Input value={draft.correlation_id} onChange={e => setDraft({ ...draft, correlation_id: e.target.value })} /></label>
        <p className="research-hint">请求 ID 支持操作请求、模型调用及已记录的服务商编号；系统分别保留这些编号。</p><label>请求 ID<Input value={draft.request_id} onChange={e => setDraft({ ...draft, request_id: e.target.value })} /></label>


        <label>动作<Input value={draft.action} onChange={e => setDraft({ ...draft, action: e.target.value })} placeholder="例如 review.revision.created" /></label>
        <label>对象 / 关联 ID<Input value={draft.object_id} onChange={e => setDraft({ ...draft, object_id: e.target.value })} /></label>
        <label>操作者 ID<Input value={draft.actor_id} onChange={e => setDraft({ ...draft, actor_id: e.target.value })} /></label>
</div></details><div className="toolbar"><Button>应用筛选</Button><Button type="button" onClick={() => { setCursors([null]); void events.refetch(); void summary.refetch(); }}>刷新记录</Button><a href={"/v1/research/audit-events/export?" + base}>导出筛选结果 JSON</a><a href={"/v1/research/audit-events/export?" + base + "&format=log"}>导出格式化日志</a></div></form>
    </Card>
    {(filter.object_id || filter.correlation_id || filter.request_id) && <p>当前按指定工作或调用筛选。<Button onClick={() => { const next = { ...filter, object_id: "", correlation_id: "", request_id: "" }; setFilter(next); setDraft(next); setCursors([null]); }}>取消编号筛选</Button></p>}
    <Card><h3>当前筛选概览</h3><div className="research-audit-summary"><strong>共 {summary.data?.total ?? "—"} 条</strong>{Object.entries(outcomes).map(([k,v]) => <span key={k}>{v}：{summary.data?.outcomes[k] || 0}</span>)}</div>
      {!!summary.data && <div><SearchableSelect label={<>聚合维度</>} value={groupBy} onChange={e => setGroupBy(e.target.value)}>{[["day","日期（SGT）"],["product","产品"],["action","动作"],["actor","操作者"],["outcome","结果"]].map(([k,v]) => <option key={k} value={k}>{v}</option>)}</SearchableSelect><ul aria-label="日志聚合结果">{<Paged items={Object.entries(summary.data.groups)} label="审计分组" layout="list">{(pageItems) => pageItems.map(([name,count]) => <li key={name}>{groupBy === "action" ? actionName(name) : groupBy === "product" ? products[name] || name : groupBy === "outcome" ? outcomes[name] || name : name}：{count} 条</li>)}</Paged>}</ul></div>}<ErrorText error={summary.error} /></Card>
    <Card><div className="toolbar"><h3>{filter.object_id ? "对象操作历史" : "全部操作记录"}</h3><Button aria-pressed={mode === "table"} onClick={() => setMode("table")}>表格</Button><Button aria-pressed={mode === "timeline"} onClick={() => setMode("timeline")}>时间线</Button><Button aria-pressed={mode === "logs"} onClick={() => setMode("logs")}>格式化日志</Button></div>
      {events.isPending && <p>正在读取审计记录…</p>}<ErrorText error={events.error} />
      {events.data && !events.data.items.length && <p>当前筛选暂无操作记录。旧版本未记录的行为不会自动补造。</p>}
      {mode === "logs" ? <div className="research-audit-logs">{events.data?.items.map(e => <div key={e.id}><pre className="research-markdown">{e.formatted_log}</pre><Button onClick={() => setSelected(e.id)}>查看这次操作</Button></div>)}</div> : mode === "table" ? <div className="research-table-wrap" tabIndex={0}><table><thead><tr><th>时间 / 操作者</th><th>产品 / 动作</th><th>对象 / 版本</th><th>结果 / 说明</th><th>详情</th></tr></thead><tbody>{events.data?.items.map(e => <tr key={e.id}><td>{stamp(e.occurred_at)}<br /><small>{e.actor_id} · {term(e.actor_type)}</small></td><td>{actionName(e.action)}<br /><small>{products[e.product] || e.product}</small><details><summary>系统动作</summary>{e.action}</details></td><td><Button onClick={() => object(e.object_id)}>{kindName(e.object_type)}的历史</Button>{e.context.revision != null && <small> · 第 {String(e.context.revision)} 版</small>}</td><td>{outcomes[e.outcome] || e.outcome}<br />{e.reason}</td><td><Button onClick={() => setSelected(e.id)}>查看这次操作</Button></td></tr>)}</tbody></table></div> : <ol className="research-audit-timeline">{events.data?.items.map(e => <li key={e.id}><time>{stamp(e.occurred_at)}</time><h4>{actionName(e.action)} · {outcomes[e.outcome] || e.outcome}</h4><p>{e.actor_id} · {kindName(e.object_type)} · {e.reason}</p><Button onClick={() => setSelected(e.id)}>查看这次操作</Button></li>)}</ol>}
      <div className="toolbar"><Button disabled={cursors.length === 1} onClick={() => setCursors(previous => previous.slice(0, -1))}>上一页</Button><span>第 {cursors.length} 页</span><Button disabled={!events.data?.next_cursor} onClick={() => setCursors(previous => [...previous, events.data!.next_cursor])}>下一页</Button></div>
    </Card>
    {selected && <FocusDialog title="操作审计详情" close={() => setSelected("")} drawer>{detail.isPending ? <p>正在加载…</p> : detail.data ? <>
      <p>{stamp(detail.data.occurred_at)} · {detail.data.actor_id} · {outcomes[detail.data.outcome]}</p><h3>{actionName(detail.data.action)}</h3><p>{detail.data.reason || "未附加说明"}</p>
      <div className="toolbar"><ObjectLink id={detail.data.object_id} /></div><details><summary>查看具体修改内容</summary><JsonView value={detail.data.changes} /></details><details><summary>排查用技术信息</summary><pre className="research-markdown">{detail.data.formatted_log}</pre><JsonView value={detail.data.context} /><p>系统动作：{detail.data.action}</p></details>
      {typeof detail.data.context.sample_id === "string" && <p><a href={"/review.html?sample=" + encodeURIComponent(detail.data.context.sample_id)}>打开样本与图片 →</a></p>}
      <div className="toolbar">{Object.entries(detail.data.context).filter(([k,v]) => ["sample_id","release_id","batch_id","run_id","job_id","prompt_id"].includes(k) && typeof v === "string").map(([k,v]) => <Button key={k} onClick={() => { object(String(v)); setSelected(""); setMode("timeline"); }}>查看{({sample_id:"样本",release_id:"发布版本",batch_id:"生成批次",run_id:"评测",job_id:"后台任务",prompt_id:"规则"} as Record<string,string>)[k]}的操作历史</Button>)}{Array.isArray(detail.data.context.sample_ids) && <Paged items={detail.data.context.sample_ids} label="关联样本" layout="block">{(pageItems) => pageItems.map(id => <Button key={String(id)} onClick={() => { object(String(id)); setSelected(""); setMode("timeline"); }}>查看相关样本的操作历史</Button>)}</Paged>}</div>
      <Button onClick={() => { object(String(detail.data?.context.sample_id || detail.data?.object_id)); setSelected(""); setMode("timeline"); }}>查看对象时间线</Button>
      {detail.data.parent_event_id && <Button onClick={() => setSelected(detail.data!.parent_event_id!)}>查看父事件</Button>}<details><summary>调用编号与记录位置</summary><p>操作请求：{detail.data.request_id || "未记录"}<br />模型调用：{String(detail.data.context.model_call_id || (detail.data.object_type === "evaluation.request" ? detail.data.object_id : "未记录"))}<br />服务商编号：{String(detail.data.context.provider_request_id || "未记录")}<br />过程：{detail.data.correlation_id || "—"}<br />结果引用：{detail.data.result_ref || "—"}</p></details>
    </> : null}<ErrorText error={detail.error} /></FocusDialog>}
  </>;
}
