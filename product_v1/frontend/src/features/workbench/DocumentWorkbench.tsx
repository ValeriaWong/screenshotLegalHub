import { DocumentControls, type DocumentJob } from "./DocumentControls";
import { Paged, SearchableSelect } from "../../components/collections";
import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import { Button, Card, Input } from "../../components/ui";
import { Feedback } from "../../components/feedback";
import type { components } from "../../api/schema";
interface DocumentRow { id: string; filename: string; suffix: string; status: string; parsed_pages: number; total_pages: number | null; blocks: number; error: string | null; warning?: string; producer?: string; parser?: string; profile_digest?: string; parse_profile?: { options?: { text_chunk_chars?: number } } }
interface Block { id: string; ordinal: number; page: number; type: string; text: string; bbox: number[] | null; locator: string; table_rows?: string[][]; table_cells?: {row:number;column:number;row_span:number;column_span:number;text:string;header:boolean}[] }
interface Note { revision: number; text: string; cursor: number }
interface Analysis { id: string; status: string; block_ids: string[]; result: { summary: string; citations: string[]; uncertainties?: string[] } | null; error?: string }
interface Reading { document: DocumentRow; items: Block[]; total: number; next_offset: number | null; note: Note; analyses: Analysis[]; jobs?: DocumentJob[]; publications?: {id:string;status:string;error?:string|null}[] }
function parseLabel(row:DocumentRow){return row.parser?.startsWith("docling") ? "Docling" : row.parser?.startsWith("native-text") ? "文本分块 "+(row.parse_profile?.options?.text_chunk_chars || 1600)+" 字" : row.parser?.startsWith("paddle") ? "Paddle" : "MinerU";}
const statuses: Record<string,string> = { interrupted:"解析中断，可继续", pending:"尚未解析", parsing:"解析中", partial:"已保存部分页面", complete:"解析完成", failed:"当前窗口失败，可重试", running:"结果待确认", unknown:"结果未知，重试可能再次计费" };
export function DocumentWorkbench({ caseId, userId, readOnly, evidence }: { caseId: string; userId: string; readOnly: boolean; evidence: components["schemas"]["EvidenceItem"][] }) {
  const [open,setOpen]=useState(() => !!new URLSearchParams(location.search).get("document"));
  return <Card><h2>资料整理与原文定位</h2><p>整理 PDF、Office、图片和文本。按段阅读、保存批注，并回到原文位置。</p><Button aria-expanded={open} onClick={() => setOpen(v => !v)}>{open ? "收起资料工作区" : "打开资料工作区"}</Button>
    {open && <DocumentLibrary caseId={caseId} userId={userId} readOnly={readOnly} evidence={evidence} />}
  </Card>;
}
function DocumentLibrary({caseId,userId,readOnly,evidence}: {caseId:string;userId:string;readOnly:boolean;evidence:components["schemas"]["EvidenceItem"][]}) {
  const client=useQueryClient(), initial=new URLSearchParams(location.search);
  const [docId,setDocId]=useState(initial.get("document") || ""), [offset,setOffset]=useState(Math.floor(Number(initial.get("block") || 0)/20)*20), [selected,setSelected]=useState<number | null>(initial.has("block") ? Number(initial.get("block")) : null);
  const [search,setSearch]=useState(""), [q,setQ]=useState(""), [busy,setBusy]=useState(false), [error,setError]=useState(""), [uploadNotice,setUploadNotice]=useState(""), [mainRun,setMainRun]=useState("");
  const root="/cases/"+caseId+"/documents";
  const docs=useQuery({queryKey:["documents",caseId],queryFn:()=>api<DocumentRow[]>(root),refetchInterval:busy ? 1500 : false});
  const detail=useQuery({queryKey:["documents",caseId,docId,offset,q],queryFn:()=>api<Reading>(root+"/"+docId+"?"+new URLSearchParams({offset:String(offset),limit:"20",q})),enabled:!!docId,refetchInterval:query => busy || query.state.data?.document.status==="parsing" || query.state.data?.jobs?.some(j=>["queued","running"].includes(j.status)) ? 1500 : false});
  const currentDocument=detail.data?.document;
  useEffect(()=>{if(currentDocument)client.setQueryData<DocumentRow[]>(["documents",caseId],rows=>rows?.map(row=>row.id===currentDocument.id ? currentDocument : row));},[currentDocument,client,caseId]);
  const models=useQuery({queryKey:["models"],queryFn:()=>api<{id:string;name:string}[]>("/settings/models"),enabled:!!docId && !readOnly});
  const [model,setModel]=useState(""),[instruction,setInstruction]=useState("概括本段事实、关键数据与不确定项，并引用原文。");
  async function refresh(){await client.invalidateQueries({queryKey:["documents",caseId]});}
  function choose(id:string,block=0){setDocId(id);setOffset(Math.floor(block/20)*20);setSelected(block);setQ("");setSearch("");setError("");const url=new URL(location.href);url.searchParams.set("document",id);url.searchParams.set("block",String(block));history.replaceState(null,"",url);}
  async function action(fn:()=>Promise<unknown>){setBusy(true);setError("");try{await fn();await refresh();}catch(e){setError(String(e));}finally{setBusy(false);}}
  const sourceRef=useRef<HTMLElement>(null);
  const d=detail.data, block=d?.items.find(b=>b.ordinal===selected) || d?.items[0];
  useEffect(()=>{ if (block && selected!==null && block.ordinal===selected) { sourceRef.current?.scrollIntoView({block:"start"});sourceRef.current?.focus({preventScroll:true}); } },[block,selected]);
  return <section aria-label="资料整理工作区">
    <p>本地解析不会上传资料到模型服务。模型分析由你选择模型后单独触发，可能产生费用。扫描件解析取决于已部署的解析器；Office 页码是逻辑单元。</p>
    {!readOnly && <><label>添加资料（可多选）<Input type="file" multiple accept=".pdf,.png,.jpg,.jpeg,.webp,.docx,.xlsx,.pptx,.txt,.md,.csv" disabled={busy} onChange={async e=>{
      const files=Array.from(e.target.files || []); e.target.value="";
      await action(async()=>{let success=0;const failed:string[]=[];for(const file of files){try{const form=new FormData();form.append("file",file);const response=await fetch("/v1"+root,{method:"POST",body:form});if(!response.ok)throw new Error((await response.json()).detail || response.statusText);const uploaded=await response.json() as DocumentRow;success++;choose(uploaded.id);}catch(err){failed.push(file.name+": "+String(err));}}setUploadNotice("已添加 "+success+" / "+files.length+" 份资料。"+failed.join("；"));});
    }} /></label>
    {evidence.length>0 && <details><summary>从已有案件原件添加</summary><ul><Paged items={evidence} label="可整理原件" layout="list">{pageItems=>pageItems.map(item=><li key={item.id}>{item.filename} <Button disabled={busy} onClick={()=>action(async()=>{const row=await api<DocumentRow>(root+"/from-evidence/"+item.id,{});choose(row.id);})}>整理此原件</Button></li>)}</Paged></ul></details>}</>}
    {uploadNotice && <p role="status">{uploadNotice}</p>}
    {docs.isPending && <Feedback state="loading" />}
    {docs.error && <Feedback state="error" error={String(docs.error)} retry={()=>docs.refetch()} />}
    <SearchableSelect label="选择资料" value={docId} onChange={e=>choose(e.target.value)}><option value="">请选择资料</option>{docs.data?.map(row=><option key={row.id} value={row.id}>{row.filename} · {parseLabel(row)} · {statuses[row.status] || row.status}</option>)}</SearchableSelect>
    {docId && detail.isPending && <Feedback state="loading" />}
    {detail.error && <Feedback state="error" error={String(detail.error)} retry={()=>detail.refetch()} />}
    {d && <>
      <div className="toolbar"><strong>{d.document.filename}</strong><span role="status">{statuses[d.document.status] || d.document.status} · 已解析 {d.document.parsed_pages} / {d.document.total_pages ?? "?"} 页 · {d.document.blocks} 块</span><a href={"/v1"+root+"/"+docId+"/file"} target="_blank" rel="noreferrer">打开原文件</a>
        {!readOnly && d.document.status === "complete" && <><Button disabled={busy} onClick={() => action(async () => { const run = await api<{id:string}>("/cases/"+caseId+"/analysis/runs", {document_ids:[docId]}); setMainRun(run.id); await client.invalidateQueries({queryKey:["refs",caseId]}); })}>加入主流程事实整理</Button><a href={"/evaluation.html?view=agents&case="+encodeURIComponent(caseId)}>对照论文方法</a></>}
        {!readOnly && d.document.status!=="complete" && <Button disabled={busy || d.document.status==="parsing" || d.jobs?.some(j=>["queued","running"].includes(j.status))} aria-busy={busy} onClick={()=>action(()=>api(root+"/"+docId+"/parse-jobs",{pages:3,all_pages:false}))}>{d.document.status==="failed" ? "重试当前解析窗口" : "解析下一段（最多 3 页）"}</Button>}
      </div>
      <DocumentControls root={root} document={d.document} readOnly={readOnly} busy={busy} jobs={d.jobs || []} choose={choose} action={action} />
      {!readOnly && d.document.status!=="complete" && <Button disabled={busy || d.jobs?.some(j=>["queued","running"].includes(j.status))} onClick={()=>action(()=>api(root+"/"+docId+"/parse-jobs",{pages:3,all_pages:true}))}>解析全部剩余页面</Button>}
      {d.document.status==="complete" && <div className="toolbar"><Button disabled={readOnly || busy} onClick={()=>action(async()=>{await api(root+"/"+docId+"/publish",{});await client.invalidateQueries({queryKey:["refs",caseId]});})}>发布此解析为案件来源</Button>{d.publications?.some(p=>p.status==="published") && <span role="status">此解析快照已发布，原有版本保留</span>}</div>}
      {mainRun && <p role="status">已生成主流程运行。<a href={"/console.html?case="+encodeURIComponent(caseId)+"&tab=advanced&run="+encodeURIComponent(mainRun)}>查看计划与审核进度</a>。无领域模板时仅整理原文事实。</p>}
      {d.document.error && <p role="alert">{d.document.error}</p>}{d.document.warning && <p>{d.document.warning}</p>}
      {d.note.cursor>0 && <Button onClick={()=>choose(docId,d.note.cursor)}>继续上次阅读位置（第 {d.note.cursor+1} 块）</Button>}
      <form className="toolbar" onSubmit={e=>{e.preventDefault();setQ(search);setOffset(0);setSelected(null);}}><label>搜索已解析原文<Input value={search} onChange={e=>setSearch(e.target.value)} /></label><Button>查找原文</Button></form>
      <div className="document-reading-layout"><section aria-label="结构化原文">
        <p>匹配 {d.total} 块；点击条目定位原文。{d.document.status!=="complete" && "当前仅检索已解析页，后续页面尚未覆盖。"}</p>
        {d.items.map(item=><article key={item.id} className={"document-block"+(block?.id===item.id ? " selected" : "")}><Button aria-pressed={block?.id===item.id} onClick={()=>{setSelected(item.ordinal);sourceRef.current?.scrollIntoView({block:"start"});sourceRef.current?.focus({preventScroll:true});const url=new URL(location.href);url.searchParams.set("document",docId);url.searchParams.set("block",String(item.ordinal));history.replaceState(null,"",url);}}>定位原文 · 第 {item.page} 页 / 第 {item.ordinal+1} 块 · {item.type}</Button>{item.table_rows?.length ? <div className="document-table-scroll" tabIndex={0}><table aria-label="原文表格"><tbody>{item.table_cells?.length ? [...new Set(item.table_cells.map(c=>c.row))].map(row=><tr key={row}>{item.table_cells!.filter(c=>c.row===row).sort((a,b)=>a.column-b.column).map(c=>c.header ? <th key={c.column} rowSpan={c.row_span} colSpan={c.column_span}>{c.text}</th> : <td key={c.column} rowSpan={c.row_span} colSpan={c.column_span}>{c.text}</td>)}</tr>) : item.table_rows.map((cells,i)=><tr key={i}>{cells.map((cell,j)=><td key={j}>{cell}</td>)}</tr>)}</tbody></table></div> : <pre>{item.text}</pre>}<small>{item.locator}</small></article>)}
        <div className="toolbar"><Button disabled={offset===0} onClick={()=>{setOffset(v=>Math.max(0,v-20));setSelected(null);}}>上一段原文</Button><Button disabled={d.next_offset===null} onClick={()=>{setOffset(d.next_offset!);setSelected(null);}}>下一段原文</Button></div>
      </section><aside ref={sourceRef} tabIndex={-1} className="document-source-pane" aria-label="原文位置与批注">
        {block && <SourcePreview key={docId+":"+block.id} root={root+"/"+docId} block={block} suffix={d.document.suffix} />}
        <ReadingNote key={docId} userId={userId} caseId={caseId} docId={docId} root={root} note={d.note} cursor={block?.ordinal || 0} readOnly={readOnly} refresh={refresh} />
        {!readOnly && <section><h3>逐段模型分析</h3><p>分析从当前块开始的最多 5 块；结果须带范围内引用，仍需人工核对。</p><SearchableSelect label="分析模型" value={model} onChange={e=>setModel(e.target.value)}><option value="">选择已配置模型</option>{models.data?.map(m=><option key={m.id} value={m.id}>{m.name}</option>)}</SearchableSelect><label>本段分析要求<textarea value={instruction} onChange={e=>setInstruction(e.target.value)} /></label><Button disabled={busy || !model || !block} onClick={()=>action(()=>api(root+"/"+docId+"/analyses",{offset:block!.ordinal,limit:5,model_id:model,instruction}))}>分析当前段（发送给所选模型）</Button>{models.error && <p role="alert">{String(models.error)}</p>}</section>}
      </aside></div>
      <section><h3>已保存分析（{d.analyses.length}）</h3><Paged items={d.analyses} label="逐段分析记录" layout="block">{pageItems=>pageItems.map(a=><details key={a.id}><summary>{statuses[a.status] || (a.status==="complete" ? "分析完成，待人工核对" : a.status)} · {a.block_ids.join("、")}</summary>{a.result ? <><p className="workbench-prose">{a.result.summary}</p>{a.result.citations.map(c=><Button key={c} onClick={()=>choose(docId,Number(c.split("/block:").at(-1)))}>定位引用 {c.split("/page:").at(-1)}</Button>)}{a.result.uncertainties?.map((u,i)=><p key={i}>{u}</p>)}</> : <p>{a.error || "此调用尚无可验证结果；请先确认状态再决定是否重试。"}</p>}</details>)}</Paged></section>
    </>}
    {(error || uploadNotice.includes("Error")) && <Feedback state="error" error={error || uploadNotice} />}
  </section>;
}
function SourcePreview({root,block,suffix}:{root:string;block:Block;suffix:string}) {
  const [failed,setFailed]=useState(false),[zoom,setZoom]=useState(100),[size,setSize]=useState<[number,number]>([1,1]);
  const image=suffix===".pdf" || [".png",".jpg",".jpeg",".webp"].includes(suffix), url="/v1"+root+"/pages/"+block.page+"/image";
  return <section><h3>原文定位 · 第 {block.page} 页</h3>{image && !failed ? <>
    <label>原文缩放<select value={zoom} onChange={e=>setZoom(Number(e.target.value))}>{[100,150,200,300].map(v=><option value={v} key={v}>{v}%</option>)}</select></label>
    <div className="document-preview-scroll" tabIndex={0} aria-label="可缩放的原文页面"><div className="document-preview-stage" style={{width:zoom+"%",aspectRatio:size[0]+"/"+size[1]}}><img alt={"原文第 "+block.page+" 页"} src={url} onError={()=>setFailed(true)} onLoad={e=>setSize([e.currentTarget.naturalWidth,e.currentTarget.naturalHeight])} />{block.bbox && <svg viewBox="0 0 1000 1000" preserveAspectRatio="none" aria-label="当前原文高亮区域"><rect x={block.bbox[0]} y={block.bbox[1]} width={block.bbox[2]-block.bbox[0]} height={block.bbox[3]-block.bbox[1]} fill="var(--bbox-fill)" stroke="var(--warning)" strokeWidth={4} /></svg>}</div></div><a href={url} target="_blank" rel="noreferrer">打开原页图片</a>
  </> : <p>{failed ? "页面预览暂不可用，可打开原文件核对。" : "此格式使用逻辑页与结构块定位，可打开原文件对照；不提供物理页坐标。"}</p>}
    <p>引用：{block.locator}</p>{!block.bbox && image && <p>此块没有可靠坐标，仅定位到页面。</p>}
  </section>;
}
function ReadingNote({userId,caseId,docId,root,note,cursor,readOnly,refresh}:{userId:string;caseId:string;docId:string;root:string;note:Note;cursor:number;readOnly:boolean;refresh:()=>Promise<void>}) {
  const cache="document-note:"+userId+":"+caseId+":"+docId;
  const [draft]=useState(()=>{try{return JSON.parse(localStorage.getItem(cache)||"null") as Note | null;}catch{return null;}});
  const [text,setText]=useState(draft?.text ?? note.text),[revision,setRevision]=useState(draft?.revision ?? note.revision),[busy,setBusy]=useState(false),[error,setError]=useState(""),[status,setStatus]=useState(draft ? "已恢复本机批注草稿" : "");
  const [serverNote,setServerNote]=useState<Note | null>(null);
  return <section><h3>阅读批注与断点</h3><label>本段分析 / 阅读批注<textarea disabled={readOnly || busy} value={text} onChange={e=>{setText(e.target.value);try{localStorage.setItem(cache,JSON.stringify({text:e.target.value,revision,cursor}));setStatus("批注已缓存在本机，点击保存后同步服务器");}catch{setStatus("本机缓存失败，请及时保存");}}} /></label><Button disabled={readOnly || busy} onClick={async()=>{setBusy(true);setError("");try{const saved=await api<Note>(root+"/"+docId+"/note",{expected_revision:revision,text,cursor},"PUT");setRevision(saved.revision);try{localStorage.removeItem(cache);}catch{ /* Server save already succeeded. */ }setStatus("批注和阅读位置已保存");await refresh();}catch(e){setError(String(e));}finally{setBusy(false);}}}>保存批注与阅读位置</Button><Button disabled={busy} onClick={async()=>{setBusy(true);setError("");try{const latest=await api<Reading>(root+"/"+docId+"?limit=1");setServerNote(latest.note);}catch(e){setError(String(e));}finally{setBusy(false);}}}>比对服务器批注</Button>{serverNote && <aside aria-label="服务器批注版本"><h4>服务器版本 {serverNote.revision}</h4><p className="workbench-prose">{serverNote.text || "服务器批注为空"}</p><p>对照上方草稿手工合并后，可采用此版本作为保存基线。</p><Button disabled={readOnly || busy} onClick={()=>{setRevision(serverNote.revision);try{localStorage.setItem(cache,JSON.stringify({text,revision:serverNote.revision,cursor}));}catch{ /* Existing text stays in this editor. */ }setServerNote(null);setStatus("当前文本已保留，请核对合并后再次保存");}}>使用该版本作为保存基线，保留当前文本</Button></aside>}<p role="status">{status}</p>{error && <p role="alert">{error}</p>}</section>;
}
