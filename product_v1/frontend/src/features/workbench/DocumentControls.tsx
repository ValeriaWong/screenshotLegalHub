import type { components } from "../../api/schema";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import { Button, Input } from "../../components/ui";
type Parser = components["schemas"]["ParserCapabilities"];
export type DocumentJob = components["schemas"]["ParseJobView"];
export function DocumentControls({root,document,readOnly,busy,jobs,choose,action}:{root:string;document:{id:string;suffix:string;parser?:string;profile_digest?:string};readOnly:boolean;busy:boolean;jobs:DocumentJob[];choose:(id:string)=>void;action:(fn:()=>Promise<unknown>)=>Promise<void>}) {
  const [parser,setParser]=useState("auto"),[chunk,setChunk]=useState(1600);
  const available=useQuery({queryKey:["document-parsers"],queryFn:()=>api<Parser[]>("/document-parsers")});
  const active=jobs.find(j=>["queued","running"].includes(j.status));
  return <section aria-label="解析版本与任务">
    {active && <div role="status"><p>{active.cancel_requested ? "正在停止后续页面，当前窗口完成后保留结果" : active.status==="queued" ? "解析任务已排队，关闭或刷新页面后仍可继续" : "正在解析，已提交的页面已保存"}</p><progress aria-label="解析进度" max={active.total_pages || 1} value={active.parsed_pages} /><p>{active.parsed_pages} / {active.total_pages ?? "?"} 页</p><Button disabled={readOnly || active.cancel_requested || busy} onClick={()=>action(()=>api(root.replace(/\/documents$/,"/document-jobs")+"/"+active.id+"/cancel",{}))}>停止后续解析</Button></div>}
    {jobs[0]?.status==="failed" && <p role="alert">{jobs[0].error?.message || "解析失败，已提交页面保留"}</p>}
    <details><summary>解析版本与对照配置</summary><p>当前解析：{document.parser || "历史配置"}{document.profile_digest ? " · "+document.profile_digest.slice(0,12) : ""}。新配置产生独立版本，已有引用保留。</p>
      <label>新版本解析器<select value={parser} disabled={readOnly || busy || !!active} onChange={e=>setParser(e.target.value)}><option value="auto">沿用默认解析</option>{available.data?.map(p=><option key={p.id} value={p.id} disabled={!p.available || !p.formats.includes(document.suffix)}>{p.name}{!p.available ? "（未部署）" : !p.formats.includes(document.suffix) ? "（此配置不支持当前格式）" : ""}</option>)}</select></label>
      {[".txt",".md"].includes(document.suffix) && <label>文本分块字符数<Input type="number" min={200} max={8000} value={chunk} onChange={e=>setChunk(Number(e.target.value))} /></label>}
      {available.data?.find(p=>p.id===parser)?.description && <p>{available.data.find(p=>p.id===parser)!.description}</p>}
      {available.error && <p role="alert">{String(available.error)}</p>}
      <Button disabled={readOnly || busy || !!active} onClick={()=>action(async()=>{const row=await api<{id:string}>(root+"/"+document.id+"/parse-runs",{parser,text_chunk_chars:chunk});choose(row.id);})}>创建独立解析版本</Button>
    </details>
  </section>;
}
