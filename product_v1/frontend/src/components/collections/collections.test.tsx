import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { useState } from "react";
import { I18nProvider } from "../../i18n";
import { Paged, SearchableSelect } from "./index";
import { CommentHistory } from "../../features/research/CommentHistory";
import type { ReviewComment } from "../../features/research/client";
afterEach(() => { cleanup(); localStorage.clear(); });
const items = Array.from({length:137}, (_,i) => ({id:"item-"+(i+1),title:"记录 "+(i+1)}));
function Selection() {
 const [selected,setSelected]=useState<string[]>([]);
 return <I18nProvider><form><Paged items={items} label="测试记录">{page => page.map(item=><label key={item.id}><input type="checkbox" checked={selected.includes(item.id)} onChange={e=>setSelected(v=>e.target.checked?[...v,item.id]:v.filter(id=>id!==item.id))}/>{item.title}</label>)}</Paged><output>{selected.join(",")}</output></form></I18nProvider>;
}
describe("bounded collections", () => {
 it("bounds rendered rows and preserves cross-page selection while searching the complete collection", () => {
  render(<Selection/>);
  expect(screen.getAllByRole("checkbox")).toHaveLength(20);
  fireEvent.click(screen.getByRole("checkbox",{name:"记录 1"}));
  fireEvent.click(screen.getByRole("button",{name:"下一页：测试记录"}));
  fireEvent.click(screen.getByRole("checkbox",{name:"记录 21"}));
  expect(screen.getByRole("status")).toHaveTextContent("item-1,item-21");
  fireEvent.change(screen.getByRole("searchbox",{name:"搜索测试记录"}),{target:{value:"记录 137"}});
  expect(screen.getAllByRole("checkbox")).toHaveLength(1);
  fireEvent.click(screen.getByRole("checkbox",{name:"记录 137"}));
  fireEvent.change(screen.getByRole("searchbox",{name:"搜索测试记录"}),{target:{value:"记录 1"}});
  expect(screen.getByRole("checkbox",{name:"记录 1"})).toBeChecked();
  expect(screen.getByRole("status")).toHaveTextContent("item-1,item-21,item-137");
  for(const button of screen.getAllByRole("button"))expect(button).toHaveAttribute("type","button");
 });
 it("anchors deep-linked records, preserves position when resizing, and clamps after data shrinks", () => {
  const ui=(data:typeof items)=><I18nProvider><Paged items={data} label="定位记录" anchorIndex={60}>{page=>page.map(i=><p key={i.id}>{i.title}</p>)}</Paged></I18nProvider>;
  const view=render(ui(items));
  expect(screen.getByText("记录 61",{exact:true})).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("每页"),{target:{value:"50"}});
  expect(screen.getByText("记录 61",{exact:true})).toBeInTheDocument();
  view.rerender(ui(items.slice(0,4)));
  expect(screen.getByText("记录 4",{exact:true})).toBeInTheDocument();
  expect(screen.queryByText("记录 61",{exact:true})).not.toBeInTheDocument();
 });
 it("reaches the final page and recovers from a zero-match search", () => {
  render(<I18nProvider><Paged items={items} label="跳页记录">{page=>page.map(i=><p key={i.id}>{i.title}</p>)}</Paged></I18nProvider>);
  fireEvent.change(screen.getByLabelText("跳至页"),{target:{value:"7"}});
  fireEvent.click(screen.getByRole("button",{name:"前往"}));
  expect(screen.getByText("记录 137",{exact:true})).toBeInTheDocument();
  expect(screen.getByRole("button",{name:"下一页：跳页记录"})).toBeDisabled();
  fireEvent.change(screen.getByRole("searchbox"),{target:{value:"没有匹配"}});
  expect(screen.getByText("没有匹配项，请调整关键词。")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button",{name:"清除搜索"}));
  expect(screen.getByText("记录 1",{exact:true})).toBeInTheDocument();
 });
 it("keeps paging controls when a smaller page size outlives a shrinking dataset", () => {
  const ui=(data:typeof items)=><I18nProvider><Paged items={data} label="变化列表">{page=>page.map(i=><p key={i.id}>{i.title}</p>)}</Paged></I18nProvider>;
  const view=render(ui(items));
  fireEvent.change(screen.getByLabelText("每页"),{target:{value:"10"}});
  view.rerender(ui(items.slice(0,15)));
  fireEvent.click(screen.getByRole("button",{name:"下一页：变化列表"}));
  expect(screen.getByText("记录 15")).toBeInTheDocument();
 });
 it("locates an asynchronously loaded selected row without overriding subsequent manual paging", () => {
  const ui=(data:typeof items)=><I18nProvider><Paged items={data} label="异步定位" anchorIndex={data.findIndex(i=>i.id==="item-91")}>{page=>page.map(i=><p key={i.id}>{i.title}</p>)}</Paged></I18nProvider>;
  const view=render(ui([])); view.rerender(ui(items));
  expect(screen.getByText("记录 91")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button",{name:"上一页：异步定位"}));
  view.rerender(ui([...items]));
  expect(screen.getByText("记录 61")).toBeInTheDocument();
  expect(screen.queryByText("记录 91")).not.toBeInTheDocument();
 });
 it("bounds native options without losing the current selection or disabled placeholders", () => {
  function Picker(){const [value,setValue]=useState("180");return <I18nProvider><SearchableSelect label="案件" required value={value} onChange={e=>setValue(e.target.value)}><option value="" disabled>选择案件</option>{Array.from({length:205},(_,i)=><option key={i+1} value={i+1}>案件 {i+1}</option>)}</SearchableSelect></I18nProvider>;}
  render(<Picker/>);
  const picker=screen.getByRole("combobox",{name:"案件"});
  expect(picker).toHaveValue("180");
  expect(within(picker).getAllByRole("option").length).toBeLessThanOrEqual(52);
  expect(within(picker).getByRole("option",{name:"选择案件"})).toBeDisabled();
  fireEvent.change(screen.getByRole("searchbox",{name:"搜索案件"}),{target:{value:"案件 205"}});
  expect(within(picker).getByRole("option",{name:"案件 180"})).toBeInTheDocument();
  fireEvent.change(picker,{target:{value:"205"}});
  expect(picker).toHaveValue("205");
  fireEvent.change(screen.getByRole("searchbox",{name:"搜索案件"}),{target:{value:"不存在"}});
  expect(picker).toHaveValue("205");
 });
 it("does not count a pinned nonmatching case as a search result", () => {
  const view=render(<I18nProvider><SearchableSelect label="匹配案件" value="keep" pinnedValue="keep" onChange={()=>{}}><optgroup label="当前选中"><option value="keep">保留当前案件</option></optgroup>{Array.from({length:100},(_,i)=><option key={i} value={String(i)}>匹配案件 {i}</option>)}</SearchableSelect></I18nProvider>);
  expect(view.container.querySelector(".collection-count")?.textContent).toContain("/ 100");
  expect(screen.getByRole("combobox",{name:"匹配案件"})).toHaveValue("keep");
 });
 it("preserves comment edits when the row leaves and re-enters its page", () => {
  const comments=Array.from({length:25},(_,i)=>({id:"comment-"+i,sample_id:"sample",revision:1,body:"评论 "+i,state:"open",applicability:"revision",use_for_generation:true,created_at:"2026-10-25T00:00:00Z"})) as ReviewComment[];
  render(<I18nProvider><CommentHistory comments={comments} refresh={async()=>{}}/></I18nProvider>);
  const row=screen.getByText("评论 0",{selector:"p"}).closest("article")!;
  fireEvent.click(within(row).getByText("处理 / 修订这条评论"));
  fireEvent.change(within(row).getByLabelText("修订评论正文"),{target:{value:"未提交的修订"}});
  fireEvent.change(within(row).getByLabelText("处理原因 / 验证依据"),{target:{value:"未提交的依据"}});
  fireEvent.click(screen.getByRole("button",{name:"下一页：评论记录"}));
  expect(screen.queryByText("评论 0",{selector:"p"})).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button",{name:"上一页：评论记录"}));
  const restored=screen.getByText("评论 0",{selector:"p"}).closest("article")!;
  expect(within(restored).getByLabelText("修订评论正文")).toHaveValue("未提交的修订");
  expect(within(restored).getByLabelText("处理原因 / 验证依据")).toHaveValue("未提交的依据");
 });
});
