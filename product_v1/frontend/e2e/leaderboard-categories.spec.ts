import { test,expect,artifactPath } from "./fixtures";
import { execFileSync } from "node:child_process";
import path from "node:path";
test("four leaderboard categories compare models or methods and retain Agent pending quality",async({page,request})=>{
  test.setTimeout(90000);
  const cid=(await(await request.post("/v1/cases",{data:{title:"Categorized comparison fixture"}})).json()).id;
  const doc=await(await request.post("/v1/cases/"+cid+"/documents",{multipart:{file:{name:"case.txt",mimeType:"text/plain",buffer:Buffer.from("Synthetic case: a transfer of 520 CNY is recorded; legal meaning is uncertain.")}}})).json();
  expect((await request.post("/v1/cases/"+cid+"/documents/"+doc.id+"/parse-next",{data:{pages:3}})).ok()).toBeTruthy();
  const script=[
    "import os,sys",
    "from pathlib import Path",
    "os.environ['DATA_DIR']=os.environ['E2E_DATA_DIR']",
    "sys.path.insert(0,str(Path('../backend/tests').resolve()))",
    "from test_leaderboard_categories import benchmark,pipeline,save,agent,REACT,REFINE",
    "from screenshotlegal.research.store import Store",
    "from screenshotlegal.settings import Settings",
    "from screenshotlegal.infrastructure.db.repository import Repository",
    "from screenshotlegal.application.services.workspace import Workspace",
    "from screenshotlegal.documents.service import Documents",
    "from screenshotlegal.experiments.inputs import FrozenInputBuilder",
    "from screenshotlegal.experiments.registry import CandidateRegistry",
    "settings=Settings();repo=Repository(settings.database_url);workspace=Workspace(settings,repo)",
    "store=Store(settings.data_dir)",
    "benchmark(store,'browser-m01',REACT,score=1)",
    "benchmark(store,'browser-m02',REFINE,score=.5)",
    "benchmark(store,'browser-m03',dict(id='E00',name='One-shot'),score=0)",
    "p,ss,n=pipeline(store,'browser-enhanced');n['variant']='reference_guided_prediction';save(store,'benchmark.pipeline.node',n)",
    "case=repo.get('cases',"+JSON.stringify(cid)+")",
    "f=FrozenInputBuilder(workspace,Documents(workspace)).build(case,'Synthetic source comparison',["+JSON.stringify(doc.id)+"],'2026-10-29');f['id']=f['input_digest']",
    "registry=CandidateRegistry();save(store,'agent.input',f)",
    "for mid in ['E00','E02','E06']:",
    " row=agent(store,'browser-agent-'+mid,mid,case=case['id'],input_id=f['id'],input_digest=f['input_digest'],case_title=case['title'],protocol_digest=registry.code_digest,method=registry.method(mid),output=None,perception_digest=f['perception_digest'],matterpack_digest=f['matterpack_digest'],legal_corpus_digest=f['legal_corpus_digest'])",
    "with store.tx() as db:",
    " for kind in ['benchmark.run','benchmark.attempt','benchmark.score','benchmark.pipeline','benchmark.pipeline.node','benchmark.pipeline.task','benchmark.scoreset','agent.input','agent.run']:",
    "  db.execute('UPDATE records SET owner=? WHERE kind=? AND owner=?',('e2eadmin',kind,'alice'))",
    "store.close();repo.engine.dispose()"
  ].join("\n");
  execFileSync(path.resolve("../.conda/screenshotlegal-v1/python.exe"),["-X","utf8","-c",script],{windowsHide:true});
  const errors:string[]=[];page.on("pageerror",e=>errors.push(e.message));
  await page.goto("/evaluation.html?view=leaderboard");
  const categories=page.getByRole("navigation",{name:"比较类别"});
  await expect(categories.getByRole("button")).toHaveCount(4);
  expect((await categories.boundingBox())!.width).toBeGreaterThan(800);
  expect((await categories.getByRole("button").first().boundingBox())!.width).toBeGreaterThan(150);
  await expect(categories.getByRole("button",{name:/单模型 One-shot/})).toHaveAttribute("aria-pressed","true");
  await categories.getByRole("button",{name:/KIE 增强/}).click();
  const table=page.getByRole("region",{name:"可滚动的模型排名表"});
  await expect(table.getByRole("row",{name:/Alpha/})).toBeVisible();
  await expect(page.getByRole("combobox",{name:"比较方式",exact:true})).toHaveValue("models");
  await expect(page).toHaveURL(/board_category=kie_enhanced/);
  await categories.getByRole("button",{name:/推断方法复现/}).click();
  await expect(page.getByRole("combobox",{name:"比较方式",exact:true})).toHaveValue("methods");
  await expect(page.getByLabel("显示同条件 One-shot 对照基线",{exact:true})).toBeChecked();
  await expect(table.getByRole("row",{name:/Self-Refine/})).toContainText("50.0%");
  await expect(table.getByRole("row",{name:/ReAct/})).toContainText("100.0%");
  await expect(table.getByRole("row",{name:/One-shot/}).filter({hasText:"对照基线"})).toHaveCount(1);
  const ids=await table.locator("tbody tr:not([data-catalogue])").count();expect(ids).toBe(3);
  await page.screenshot({path:artifactPath("method-reproductions-desktop.png"),fullPage:true});
  await page.getByRole("combobox",{name:"榜单性质",exact:true}).selectOption("development");
  await categories.getByRole("button",{name:/^Agent/}).click();
  await expect(page.getByText("过程对比 · 质量待评",{exact:true})).toBeVisible();
  await expect(table.locator("tbody tr:not([data-catalogue])")).toHaveCount(3);
  await expect(table).toContainText("模型 3 · 工具 2");
  await expect(table).toContainText("待专家金标");
  await expect(table.getByRole("progressbar")).toHaveCount(0);
  await page.screenshot({path:artifactPath("agent-methods-desktop.png"),fullPage:true});
  await page.setViewportSize({width:375,height:812});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  await page.screenshot({path:artifactPath("leaderboard-categories-mobile.png"),fullPage:true});
  await page.setViewportSize({width:844,height:390});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  await page.setViewportSize({width:1280,height:900});
  const source=table.locator('a[href*="agent_run=browser-agent-E02"]');
  await source.click();
  await expect(page).toHaveURL(/agent_run=browser-agent-E02/);
  await expect(page.getByRole("heading",{name:/E02 · e02_staged_without_matterpack/})).toBeVisible();
  await expect(page.getByRole("link",{name:/导出论文实验原始记录/})).toBeVisible();
  expect(errors).toEqual([]);
});
