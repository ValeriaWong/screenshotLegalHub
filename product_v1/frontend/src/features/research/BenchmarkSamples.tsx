import { Paged } from "../../components/collections";
import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Button, Card, Input } from "../../components/ui";
import { useUser } from "../auth/AuthGate";
import { api } from "./client";
import { ErrorText } from "./shared";
import { readDraft, writeDraft, draftKey } from "./benchmarkDrafts";

interface Sample { image_name: string; asset_id: string; asset_status: string; kie: number; regional_vqa: number; global_vqa: number; regions: number; maximum_calls: number; ready_for_pipeline: boolean }
export function BenchmarkSamples({ dataset, selected, onChange }: { dataset: string; selected: string[]; onChange: (names: string[]) => void }) {
  const user = useUser(), epoch = useRef(0);
  const [q, setQ] = useState(""), [search, setSearch] = useState(""), [offsets, setOffsets] = useState([0]), [ready, setReady] = useState(false), [error, setError] = useState("");
  const cacheKey = draftKey(user?.id || "", dataset, "sample-selection");
  const params = new URLSearchParams({ q: search, offset: String(offsets.at(-1)) });
  const samples = useQuery({ queryKey: ["research", "benchmark-samples", dataset, params.toString()], queryFn: () => api<{ items: Sample[]; total: number; next_offset: number | null }>("/evaluation/benchmarks/" + dataset + "/samples?" + params) });
  useEffect(() => { let active = true; void readDraft(cacheKey).then(d => { if (active && !epoch.current && Array.isArray(d?.content.image_names)) onChange(d.content.image_names.filter((v): v is string => typeof v === "string")); }).catch(e => setError(String(e))).finally(() => { if (active) setReady(true); }); return () => { active = false; }; }, [cacheKey, onChange]);
  function change(names: string[]) { epoch.current++; onChange(names); }
  useEffect(() => { if (!ready || !epoch.current) return; void writeDraft(cacheKey, { draft_id: cacheKey, base_version: 0, content: { image_names: selected }, updated_at: new Date().toISOString() }).catch(e => setError(String(e))); }, [cacheKey, selected, ready]);
  return <Card><h2>选择评测样本（图片）</h2><p>选择图片后会自动纳入该图全部题目。建议先选1–3张，再到下一步确认模型和调用范围。</p>
    <form className="toolbar" onSubmit={e => { e.preventDefault(); setSearch(q); setOffsets([0]); }}><label>搜索样本图片<Input value={q} onChange={e => setQ(e.target.value)} /></label><Button>查找样本</Button></form>
    <p role="status">已选 {selected.length} 个样本；列表共 {samples.data?.total ?? "—"} 个。已选项在搜索和翻页后保留。</p>
    {!!selected.length && <details><summary>查看或移除已选样本（{selected.length}）</summary><ul>{<Paged items={selected} label="已选样本" layout="list" searchable={false}>{(pageItems) => pageItems.map(name => <li key={name}>{name} <Button onClick={() => change(selected.filter(n => n !== name))}>移除 {name}</Button></li>)}</Paged>}</ul></details>}
    <div className="pipeline-sample-grid" role="group" aria-label="完整评测样本列表">{samples.data?.items.map(s => <article className="pipeline-sample-card" data-selected={selected.includes(s.image_name)} key={s.image_name}>
      <label><Input type="checkbox" aria-label={"选择样本 " + s.image_name} checked={selected.includes(s.image_name)} disabled={!ready || !s.ready_for_pipeline} onChange={e => change(e.target.checked ? [...selected, s.image_name] : selected.filter(n => n !== s.image_name))} /><img src={"/v1/review/assets/" + s.asset_id} alt={"样本缩略图 " + s.image_name} loading="lazy" /><span><strong>{s.image_name}</strong><small>{s.regional_vqa + s.global_vqa} 道问答 · 最多 {s.maximum_calls} 次调用</small><small>{s.regional_vqa ? s.regional_vqa + " 道区域题 · " + s.global_vqa + " 道全图题" : "仅全图题，不涉及IoU"}</small></span></label>
      {s.asset_status === "candidate_identity_unverified" && <p>补图身份待确认，默认不纳入运行</p>}{!s.ready_for_pipeline && <p>缺少唯一KIE来源，暂不能完整评测</p>}
      <a href={"/review.html?section=benchmark&benchmark=" + dataset + "&image_name=" + encodeURIComponent(s.image_name)}>核对原图与任务 →</a>
    </article>)}</div>
    {!samples.isPending && !samples.data?.items.length && <p>没有符合条件的样本，请调整图片名称。</p>}
    <div className="toolbar"><Button disabled={offsets.length === 1} onClick={() => setOffsets(v => v.slice(0,-1))}>上一页样本</Button><Button disabled={samples.data?.next_offset == null} onClick={() => setOffsets(v => [...v,samples.data!.next_offset!])}>下一页样本</Button><Button disabled={!selected.length} onClick={() => change([])}>清空样本选择</Button></div><ErrorText error={error || samples.error} />
  </Card>;
}
