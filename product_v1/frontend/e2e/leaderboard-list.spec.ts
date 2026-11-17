import { test,expect,artifactPath } from "./fixtures";
import { execFileSync } from "node:child_process";
import path from "node:path";
test("real API lists development scores and untested configurations above the fold",async({page,request})=>{
  const ids:string[]=[];
  for(const name of ["List Alpha","List Beta"]){
    const r=await request.post("/v1/settings/models",{data:{name,base_url:"https://fixture.invalid/v1",model_name:name,api_key:"synthetic-test-key",supports_vision:true,allow_external_egress:false}});
    expect(r.ok()).toBeTruthy();ids.push((await r.json()).id);
  }
  const script=[
    "import os,sys",
    "from pathlib import Path",
    "os.environ['DATA_DIR']=os.environ['E2E_DATA_DIR']",
    "sys.path.insert(0,str(Path('../backend/tests').resolve()))",
    "from test_leaderboard import pipeline,save",
    "from screenshotlegal.research.store import Store",
    "store=Store(Path(os.environ['E2E_DATA_DIR']))",
    "r,ss,n=pipeline(store,'list-current',mode='development_reference',score=.5)",
    "r['model'].update(config_id="+JSON.stringify(ids[0])+",name='List Alpha',model='List Alpha')",
    "r['created_at']='2026-10-30T00:00:00+00:00';save(store,'benchmark.pipeline',r)",
    "with store.tx() as db:",
    " db.execute(\"UPDATE records SET owner='e2eadmin' WHERE owner='alice'\")",
    "store.close()"
  ].join("\n");
  execFileSync(path.resolve("../.conda/screenshotlegal-v1/python.exe"),["-X","utf8","-c",script],{windowsHide:true});
  await page.goto("/evaluation.html?view=leaderboard&board_family=pipeline");
  const table=page.getByRole("region",{name:"可滚动的模型排名表"});
  await expect(table.getByRole("row",{name:/List Alpha/})).toContainText("50.0%");
  const beta=table.getByRole("row",{name:/List Beta/});
  await expect(beta).toContainText("未评测");
  await expect(beta.locator("td").first()).toHaveText("—");
  await expect(beta.getByRole("progressbar")).toHaveCount(0);
  await expect(page.getByRole("combobox",{name:"榜单性质",exact:true})).toHaveValue("auto");
  await expect(page.locator(".leaderboard-scope")).toHaveText("开发参考");
  const first=table.locator("tbody tr").first(), box=(await first.boundingBox())!;
  expect(box.y+box.height).toBeLessThan(page.viewportSize()!.height);
  await page.screenshot({path:artifactPath("list-first-screen.png"),fullPage:true});
  await page.getByRole("button",{name:"指标分析",exact:true}).click();
  await expect(page.getByRole("list",{name:"质量表现对比图"})).toContainText("50.0%");
  await page.getByRole("button",{name:"Token 用量",exact:true}).click();
  await expect(page.getByText("当前评测组没有可用于此图的完整记录。")).toBeVisible();
  await page.screenshot({path:artifactPath("metric-analysis.png"),fullPage:true});
  await page.getByRole("button",{name:"排行榜列表",exact:true}).click();
  await page.getByRole("combobox",{name:"榜单性质",exact:true}).selectOption("official");
  await expect(page.getByText(/正式榜尚无成绩/)).toBeVisible();
  await expect(table.getByRole("row",{name:/List Beta/})).toContainText("未评测");
  await page.getByRole("button",{name:/查看开发参考榜/}).click();
  await expect(table.getByRole("row",{name:/List Alpha/})).toContainText("50.0%");
  await page.getByRole("navigation",{name:"比较类别"}).getByRole("button",{name:/推断方法复现/}).click();
  await expect(table.locator('tr[data-catalogue="true"]').first()).toBeVisible();
  await expect(table).toContainText("未评测");
  await expect(page.getByRole("combobox",{name:"底座模型",exact:true})).toBeVisible();
  await page.setViewportSize({width:375,height:812});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  await page.screenshot({path:artifactPath("list-mobile.png"),fullPage:true});
});
