import { test,expect,artifactPath } from "./fixtures";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
test("leaderboard ranks frozen runs, filters, exports and opens source results",async({page,request})=>{
  const python=path.resolve("../.conda/screenshotlegal-v1/python.exe");
  const script=[
    "import os,sys",
    "from pathlib import Path",
    "os.environ['DATA_DIR']=os.environ['E2E_DATA_DIR']",
    "sys.path.insert(0,str(Path('../backend/tests').resolve()))",
    "from test_leaderboard import qa",
    "from screenshotlegal.research.store import Store",
    "store=Store(Path(os.environ['E2E_DATA_DIR']))",
    "qa(store,'board-a01',owner='e2eadmin')",
    "qa(store,'board-a02',scores=(1,None),statuses=('completed','failed'),owner='e2eadmin')",
    "qa(store,'board-b03','beta',owner='e2eadmin')",
    "qa(store,'board-b04','private',owner='another-owner')",
    "store.close()"
  ].join("\n");
  execFileSync(python,["-X","utf8","-c",script],{cwd:process.cwd(),windowsHide:true});
  const errors:string[]=[];page.on("pageerror",e=>errors.push(e.message));
  await page.goto("/evaluation.html?view=leaderboard&board_family=qa");
  await expect(page.getByRole("button",{name:"Leaderboard · 排行榜",exact:true})).toHaveAttribute("aria-current","page");
  const table=page.getByRole("region",{name:"可滚动的模型排名表"});
  await expect(table.locator("tbody tr:not([data-catalogue])").filter({hasText:"Beta"})).toContainText("100.0%");
  const alpha=table.locator("tbody tr:not([data-catalogue])").filter({hasText:"Alpha"});
  await expect(alpha).toContainText("50.0%");
  await expect(alpha).toContainText("同配置 2 次，采用最近一次");
  await expect(table).not.toContainText("Private");
  await expect(alpha.getByRole("link",{name:"查看运行与逐题结果 →"})).toHaveAttribute("href",/run=board-a02/);
  const downloaded=page.waitForEvent("download");
  await page.getByRole("button",{name:"导出本页 CSV",exact:true}).click();
  const csv=await downloaded;await csv.saveAs(artifactPath("leaderboard.csv"));
  const exported=fs.readFileSync(artifactPath("leaderboard.csv"),"utf8");
  expect(exported).toContain("Beta");expect(exported).not.toContain("SECRET_SENTINEL");expect(exported).not.toContain("PRIVATE_GOLD");
  await page.locator(".leaderboard-tools > summary").click();
  await page.getByLabel("搜索模型或方法",{exact:true}).fill("Alpha");
  await page.getByRole("button",{name:"查找模型或方法",exact:true}).click();
  await expect(table.locator("tbody tr:not([data-catalogue])").filter({hasText:"Beta"})).toHaveCount(0);
  await expect(alpha.locator("td").first()).toHaveText("2");
  await page.getByLabel("搜索模型或方法",{exact:true}).fill("");
  await page.getByRole("button",{name:"查找模型或方法",exact:true}).click();
  await expect(table.locator("tbody tr:not([data-catalogue])").filter({hasText:"Beta"})).toBeVisible();
  await page.screenshot({path:artifactPath("leaderboard-desktop.png"),fullPage:true});
  await page.setViewportSize({width:375,height:812});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  await table.focus();await expect(table).toBeFocused();
  await page.screenshot({path:artifactPath("leaderboard-mobile.png"),fullPage:true});
  await page.setViewportSize({width:844,height:390});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  await page.setViewportSize({width:1280,height:900});
  await alpha.getByRole("link",{name:"查看运行与逐题结果 →"}).click();
  await expect(page.getByRole("heading",{name:/board-a02/})).toBeVisible();
  await expect(page.getByRole("heading",{name:"逐题结果与错误",exact:true})).toBeVisible();
  expect((await request.get("/v1/evaluation/leaderboard?scope=official")).ok()).toBeTruthy();
  expect(errors).toEqual([]);
});
