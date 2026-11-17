import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Button, Card } from "../../components/ui";
import { api, stamp } from "./client";
import { term } from "./presentation";
import { ErrorText, Status } from "./shared";

interface Entry {
  id: string; kind: string; category: "formal" | "trial" | "capability" | "benchmark"; name: string;
  status: string; created_at: string; modes: string[]; total: number; returned: number | null;
  scoring: string; href: string; unknown: number | null;
}
interface History {
  items: Entry[]; total: number; next_offset: number | null;
  summary: { formal_runs: number; trial_flows: number; recorded_probes: number; counts: Record<string, number> };
}
export function EvaluationHistory({ selected, select }: { selected: string; select: (id: string) => void }) {
  const [category, setCategory] = useState("all");
  const [offsets, setOffsets] = useState([0]);
  const query = new URLSearchParams({ category, offset: String(offsets.at(-1)), limit: "20" });
  const history = useQuery({ queryKey: ["research", "evaluation-history", query.toString()], queryFn: () => api<History>("/evaluation/history?" + query), refetchInterval: 2500 });
  return <Card><h2>运行历史</h2>
    <p>这里同时保留整轮试跑、单次测试和正式评测。未计分试跑也有结果；正式评测需先审核并发布数据。</p>
    {history.data && <p role="status">正式评测 {history.data.summary.formal_runs} 次 · 整轮试跑 {history.data.summary.trial_flows} 轮 · 已保存试跑记录 {history.data.summary.recorded_probes} 条（整轮内的逐题记录合并展示）。{history.data.summary.counts.benchmark ? " KIE / VQA 及旧导入 " + history.data.summary.counts.benchmark + " 条。" : ""}</p>}
    <label>运行记录类型<select value={category} onChange={e => { setCategory(e.target.value); setOffsets([0]); }}>
      <option value="all">全部记录</option><option value="benchmark">KIE / VQA 与旧记录</option><option value="trial">未计分试跑</option><option value="formal">正式评测</option><option value="capability">连通性测试</option>
    </select></label>
    <ErrorText error={history.error} />
    {history.isPending ? <p>正在读取运行记录…</p> : !history.error && history.data && <>
      <div className="research-table-wrap" tabIndex={0}><table aria-label="评测与试跑运行历史"><thead><tr><th>记录</th><th>类型与状态</th><th>范围与计分</th><th>结果</th></tr></thead><tbody>
        {history.data.items.map(r => <tr key={r.kind + r.id}>
          <td>{r.name}<br /><small>{stamp(r.created_at)}</small></td>
          <td>{{ formal: "正式评测", trial: "未计分试跑", capability: "连通性测试", benchmark: "KIE / VQA 任务记录" }[r.category]}<br /><Status value={r.status} /></td>
          <td>{r.modes.length ? r.modes.map(term).join("、") : "输入模式未记录"}<br />
            {r.category === "benchmark" ? <>{r.total} 项 · {({ legacy_replay: "旧 IoU 离线回放", development_reference: "旧参考开发评分", official_reviewed: "人工发布版本", historical_unverified: "历史导入，未认证" } as Record<string, string>)[r.scoring] || r.scoring}</> : r.category === "formal" ? <>{r.total} 项任务 · 逐题查看计分情况</> : <>{r.returned == null ? "返回数量未记录" : "已返回 " + r.returned + " / " + r.total} · 未计分</>}
            {!!r.unknown && <p className="research-hint">整轮记录含 {r.unknown} 次结果未知，详见完整记录。</p>}
          </td>
          <td>{r.category === "formal" ? <Button aria-current={selected === r.id ? "true" : undefined} onClick={() => select(r.id)}>查看评测结果</Button> : <a href={r.href}>{r.category === "capability" ? "查看测试结果" : "查看试跑结果"} →</a>}</td>
        </tr>)}
      </tbody></table></div>
      {!history.data.items.length && <p>{category === "formal" ? "尚无正式评测。已有试跑请切换“全部记录”或“未计分试跑”；完成审核并发布后可创建正式评测。" : category === "all" ? "当前账号还没有保存的评测或试跑记录。" : "当前类型暂无记录，请切换查看其他类型。"}</p>}
      <div className="toolbar"><Button disabled={offsets.length === 1} onClick={() => setOffsets(v => v.slice(0, -1))}>上一页运行记录</Button><Button disabled={history.data.next_offset == null} onClick={() => setOffsets(v => [...v, history.data!.next_offset!])}>下一页运行记录</Button></div>
    </>}
  </Card>;
}
