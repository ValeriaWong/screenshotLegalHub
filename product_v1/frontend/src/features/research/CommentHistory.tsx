import { SearchableSelect } from "../../components/collections";
import { Paged } from "../../components/collections";
import { useEffect, useRef, useState } from "react";
import { Button, Input } from "../../components/ui";
import { api, key, stamp, type ReviewComment } from "./client";
import { ErrorText } from "./shared";
type CommentDraft = { body: string; status: string; reason: string; longTerm: boolean; usable: boolean; expanded: boolean };
export function CommentHistory({ comments, refresh, candidate }: { comments: ReviewComment[]; refresh: () => Promise<unknown>; candidate?: { id: string; revision: number } }) {
  const drafts = useRef(new Map<string, CommentDraft>());
  return <div className="review-comment-history"><h3>{candidate ? "本次生成采用的意见与验证" : "评论记录"}（{comments.length}）</h3>{<Paged items={comments} label="评论记录" layout="block" pageSize={10} searchable={false}>{(pageItems) => pageItems.map(c => <CommentRecord key={c.id} comment={c} refresh={refresh} candidate={candidate} drafts={drafts.current} />)}</Paged>}</div>;
}
function CommentRecord({ comment: c, refresh, candidate, drafts }: { comment: ReviewComment; refresh: () => Promise<unknown>; candidate?: { id: string; revision: number }; drafts: Map<string, CommentDraft> }) {
  const cached = drafts.get(c.id);
  const [body, setBody] = useState(cached?.body ?? c.body), [status, setStatus] = useState(cached?.status ?? c.state ?? "open"), [reason, setReason] = useState(cached?.reason ?? "");
  const [busy, setBusy] = useState(false), [error, setError] = useState("");
  const [longTerm, setLongTerm] = useState(cached?.longTerm ?? (c.applicability === "source")), [usable, setUsable] = useState(cached?.usable ?? c.use_for_generation);
  const [expanded, setExpanded] = useState(cached?.expanded ?? false);
  useEffect(() => { drafts.set(c.id, { body, status, reason, longTerm, usable, expanded }); }, [drafts, c.id, body, status, reason, longTerm, usable, expanded]);
  async function act(operation: () => Promise<unknown>) { setBusy(true); setError(""); try { await operation(); await refresh(); } catch(e) { setError(String(e)); } finally { setBusy(false); } }
  const labels: Record<string, string> = { open: "待处理", adopted: "已采纳", resolved: "已解决", rejected: "不采纳", withdrawn: "已撤回", superseded: "已被修订" };
  return <article><p>{c.body}</p><small>第 {c.revision} 版 · {c.message_id || "整条样本"} · {stamp(c.created_at)} · {c.applicability === "source" ? "后续同一来源也适用" : "仅此版本"} · {labels[c.state || "open"]} · {c.use_for_generation ? "带入后续生成" : "仅审核参考"}</small>
    {c.processing && <p>处理依据：{c.processing.reason}{c.processing.candidate_sample_id && " · 验证候选 " + c.processing.candidate_sample_id + " r" + c.processing.candidate_revision}</p>}
    {c.state !== "superseded" && <details open={expanded} onToggle={e => setExpanded(e.currentTarget.open)}><summary>处理 / 修订这条评论</summary><div className="research-form">
      <p className="research-hint">“已采纳”表示准备使用这条意见；“已解决”表示你已核查修改结果。尚未确认时请保留“待处理”。</p><SearchableSelect label={<>处理状态</>} aria-label="处理状态" value={status} onChange={e => setStatus(e.target.value)}>{Object.entries(labels).filter(([k]) => k !== "superseded").map(([k,v]) => <option key={k} value={k}>{v}</option>)}</SearchableSelect>
      <label>处理原因 / 验证依据<textarea aria-label="处理原因 / 验证依据" rows={2} value={reason} onChange={e => setReason(e.target.value)} /></label>
      {candidate && <p>本次处理对应当前候选的第 {candidate.revision} 版。<a href={"/review.html?sample=" + encodeURIComponent(candidate.id)}>打开候选核对</a>后再记录结论。</p>}
      <Button disabled={busy || !reason.trim()} onClick={() => act(() => api("/review/samples/" + c.sample_id + "/comments/" + c.id + "/process", { expected_event_id: c.state_event_id || null, status, reason, candidate_sample_id: candidate?.id || null, candidate_revision: candidate?.revision || null, idempotency_key: key() }))}>保存处理记录</Button>
      <label>修订评论正文<textarea aria-label="修订评论正文" rows={3} value={body} onChange={e => setBody(e.target.value)} /></label>
      <label className="research-check"><Input type="checkbox" checked={longTerm} onChange={e => setLongTerm(e.target.checked)} />适用于同源后续版本</label>
      <label className="research-check"><Input type="checkbox" checked={usable} onChange={e => setUsable(e.target.checked)} />用于生成迭代</label>
      <Button disabled={busy || !body.trim()} onClick={() => act(() => api("/review/samples/" + c.sample_id + "/comments", { revision: c.revision, message_id: c.message_id, body, use_for_generation: usable, applicability: longTerm ? "source" : "revision", supersedes: c.id, idempotency_key: key() }))}>保存为新评论版本</Button>
    </div></details>}<ErrorText error={error} />
  </article>;
}
