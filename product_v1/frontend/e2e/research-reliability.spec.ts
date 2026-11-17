import { test, expect, artifactPath } from "./fixtures";
import fs from "node:fs";
const id = () => crypto.randomUUID();
test("preserve newer typing while a revision save is in flight", async ({ page, request }) => {
 const c = await (await request.post("/v1/review/samples", { data: {dataset:"audit",content:{title:"audit save race",messages:[{id:"m1",text:"initial"}]},note:"audit",idempotency_key:id()} })).json();
 const sid=c.sample.id;
 await page.goto("/review.html?sample="+sid);
 const editor=page.locator("section.card").filter({has:page.getByRole("heading",{name:/图片审核/})});
 await expect(editor.getByRole("button",{name:"编辑消息 m1 第1页",exact:true})).toBeEnabled();
 await editor.getByText("样本字段、消息列表与题目",{exact:true}).click();
 const field=editor.getByRole("textbox",{name:"消息文本",exact:true});
 await field.fill("A submitted snapshot");
 let release!:()=>void; let intercepted!:()=>void;
 const gate=new Promise<void>(r=>release=r); const started=new Promise<void>(r=>intercepted=r);
 await page.route("**/v1/review/samples/"+sid,async route=>{
  if(route.request().method()!=="PUT"){await route.continue();return;}
  const response=await route.fetch(); intercepted(); await gate; await route.fulfill({response});
 });
 await editor.getByRole("button",{name:"保存新版本并渲染",exact:true}).click();
 await started;
 await field.fill("B typed during save, must remain unsaved");
 expect(await field.inputValue()).toContain("B typed during save");
 release();
 await expect(field).toHaveValue("B typed during save, must remain unsaved");
 await page.reload();
 await editor.getByText("样本字段、消息列表与题目",{exact:true}).click();
 await expect(field).toHaveValue("B typed during save, must remain unsaved");
 const result=await (await request.get("/v1/review/samples/"+sid)).json();
 const proof={submitted:"A submitted snapshot",typed_during_save:"B typed during save, must remain unsaved",displayed_after_save:await field.inputValue(),server_value:result.revision.content.messages[0].text,lost:false};
 fs.writeFileSync(artifactPath("ui-save-race.json"),JSON.stringify(proof,null,2));
});
test("switching Prompt name loads the target baseline",async({page,request})=>{
 const a="audit-A-"+id(), b="audit-B-"+id();
 for(const [name,markdown] of [[a,"# Unique Prompt A"],[b,"# Unique Prompt B"]]) await request.post("/v1/studio/prompts",{data:{name,markdown,note:"audit",expected_version:0,idempotency_key:id()}});
 await page.goto("/studio.html");
 await page.getByRole("button",{name:"生成规则与修改历史",exact:true}).click();
 await page.locator("label").filter({hasText:"查看其他规则"}).locator("select").selectOption(a);
 await page.locator("section.card").filter({has:page.getByRole("heading",{name:"迭代记录",exact:true})}).locator("details").first().locator("summary").first().click();
 await page.getByRole("button",{name:"基于此版本继续迭代",exact:true}).click();
 const text=page.getByRole("textbox",{name:"规则内容（支持 Markdown）",exact:true});
 await expect(text).toHaveValue("# Unique Prompt A");
 await page.locator("label").filter({hasText:"查看其他规则"}).locator("select").selectOption(b);
 await expect(page.locator("pre.research-markdown").filter({hasText:"# Unique Prompt B"})).toBeAttached();
 await expect(text).toHaveValue("# Unique Prompt B");
 fs.writeFileSync(artifactPath("ui-prompt-switch.json"),JSON.stringify({selected_name:b,displayed_markdown:await text.inputValue(),expected_markdown:"# Unique Prompt B",retained_previous_content:false},null,2));
});

test("bound release and evaluation appear in owner-scoped audit timeline", async ({page,request}) => {
 const payload={dataset:"audit-flow",content:{title:"审计闭环",messages:[{id:"m1",text:"收到100元"}],questions:[{id:"q1",question:"金额？",answer:"100元",gold:true,message_ids:["m1"]}]},note:"审计导入",idempotency_key:id()};
 const created=await (await request.post("/v1/review/samples",{data:payload})).json();const sid=created.sample.id;
 expect((await request.post("/v1/review/samples/"+sid+"/quality",{data:{revision:1,verdict:"pass",idempotency_key:id()}})).status()).toBe(409);
 await expect.poll(async()=> (await (await request.get("/v1/review/samples/"+sid)).json()).binding?.manifest_id).toBeTruthy();
 const detail=await (await request.get("/v1/review/samples/"+sid)).json();
 const q=await request.post("/v1/review/samples/"+sid+"/quality",{data:{revision:1,verdict:"pass",manifest_id:detail.binding.manifest_id,confirm_gold:true,score:90,process:"核对原图与证据",idempotency_key:id()}});expect(q.ok()).toBeTruthy();
 const release=await (await request.post("/v1/review/releases",{data:{name:"绑定发布",sample_ids:[sid],idempotency_key:id()}})).json();expect(release.contract).toBe("research.v2");
 const run=await request.post("/v1/evaluation/runs",{data:{name:"审计评测",release_id:release.id,model_ids:["demo"],idempotency_key:id()}});expect(run.ok()).toBeTruthy();
 await page.goto("/review.html?audit=1&object="+sid);
 await expect(page.getByRole("heading",{name:"操作审计",exact:true})).toBeVisible();
 await expect(page.getByRole("table")).toContainText("review.gold.created");
 await expect(page.getByRole("table")).toContainText("review.release.created");
 await expect(page.getByRole("table")).toContainText("evaluation.run.created");
 await page.getByRole("button",{name:"查看这次操作",exact:true}).first().click();
 await expect(page.getByRole("dialog",{name:"操作审计详情",exact:true})).toBeVisible();
 await page.getByRole("dialog").getByRole("button",{name:"查看对象时间线",exact:true}).click();
 await expect(page.locator(".research-audit-timeline")).toBeVisible();
 await page.screenshot({path:artifactPath("audit-desktop.png"),fullPage:true});
 await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
 await page.screenshot({path:artifactPath("audit-mobile.png"),fullPage:true});
});
test("comment disposition records verification against the generated candidate",async({page,request})=>{
 const source=await (await request.post("/v1/review/samples",{data:{dataset:"feedback",content:{title:"反馈源",messages:[{id:"m1",text:"原消息"}]},note:"initial",idempotency_key:id()}})).json();const sid=source.sample.id;
 const comment=await (await request.post("/v1/review/samples/"+sid+"/comments",{data:{revision:1,body:"保留未知事实",applicability:"source",idempotency_key:id()}})).json();
 const p=await (await request.post("/v1/studio/prompts",{data:{name:"feedback-"+id(),markdown:"# 依来源生成",note:"initial",expected_version:0,idempotency_key:id()}})).json();
 const b=await (await request.post("/v1/studio/batches",{data:{name:"反馈迭代",dataset:"feedback",source_sample_id:sid,source_revision:1,prompt_id:p.id,feedback_ids:[comment.id],idempotency_key:id()}})).json();
 let candidate="";await expect.poll(async()=>{const rows=await(await request.get("/v1/studio/batches")).json();candidate=rows.find((v:any)=>v.id===b.id)?.sample_ids[0];return candidate;}).toBeTruthy();
 await page.goto("/review.html?sample="+candidate);
 const history=page.locator(".review-comment-history").filter({has:page.getByRole("heading",{name:/本次生成采用的意见与验证/})});
 await history.getByText("处理 / 修订这条评论",{exact:true}).click();
 await history.getByLabel("处理状态",{exact:true}).selectOption("resolved");
 await history.getByLabel("处理原因 / 验证依据",{exact:true}).fill("已核查本候选未补造事实");
 await history.getByRole("button",{name:"保存处理记录",exact:true}).click();
 await expect(history.getByText(/处理依据：已核查本候选未补造事实/)).toBeVisible();
 const feedback=await(await request.get("/v1/studio/feedback?source_sample_id="+sid)).json();expect(feedback).toEqual([]);
 await page.screenshot({path:artifactPath("comment-verification.png"),fullPage:true});
});

test("historical geometry upgrades as a new revision without changing the sample id",async({page,request})=>{
 const imported=await (await request.post("/v1/review/import",{data:{group_id:"datasets/v2.0.0/round_001"}})).json();
 expect(imported.failed).toEqual([]);
 const original=await(await request.get("/v1/review/samples/"+imported.sample_ids[0])).json();
 const legacy=await(await request.post("/v1/review/samples",{data:{dataset:"legacy-upgrade",content:{...original.revision.content,visual_role:"synthetic_render",original_layout:[]},note:"模拟旧派生视图",idempotency_key:id()}})).json();const sid=legacy.sample.id;
 await page.goto("/review.html?sample="+sid);
 await page.getByRole("button",{name:"接入导入原图及坐标为新版本",exact:true}).click();
 await expect(page.getByRole("img",{name:/原图 r2 第1页/})).toBeVisible();
 const updated=await(await request.get("/v1/review/samples/"+sid)).json();
 expect(updated.sample.id).toBe(sid);expect(updated.revisions).toHaveLength(2);
 expect(updated.binding.asset_hashes[0]).toBe(original.revision.content.original_assets[0].sha256);
 await page.screenshot({path:artifactPath("original-upgrade.png"),fullPage:true});
});
