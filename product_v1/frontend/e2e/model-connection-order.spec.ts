import { test, expect, artifactPath } from "./fixtures";
import AxeBuilder from "@axe-core/playwright";
test("model passes sort first, capability badges survive reload and a connection edit resets them", async ({page,request}) => {
  const create=async(name:string,vision:boolean,key="e2e-placeholder")=>{
    const response=await request.post("/v1/settings/models",{data:{name,base_url:process.env.E2E_MODEL_BASE_URL!,model_name:"e2e-vision",api_key:key,supports_vision:vision,allow_external_egress:true}});
    expect(response.ok()).toBeTruthy();return response.json();
  };
  const failed=await create("排序验收 · 未连通",false,"incorrect-synthetic-key");
  const untouched=await create("排序验收 · 未测试",false);
  const partial=await create("排序验收 · 文本通过",true);
  const passed=await create("排序验收 · 已通过",false);
  for(const [model,success] of [[failed,false],[partial,true],[passed,true]] as const){
    const response=await request.post("/v1/settings/models/"+model.id+"/test",{data:{}});
    expect(response.ok()).toBeTruthy();expect((await response.json()).success).toBe(success);
  }
  await page.goto("/evaluation.html?view=models");
  await page.getByRole("button",{name:"模型设置",exact:true}).click();
  await expect(page.locator('[data-model-id="'+passed.id+'"]')).toBeVisible();
  const ids=new Set([failed.id,untouched.id,partial.id,passed.id]);
  const order=await page.locator("[data-model-id]").evaluateAll((rows,ids)=>rows.map(r=>r.getAttribute("data-model-id")!).filter(id=>ids.includes(id)),[...ids]);
  expect(order).toEqual([passed.id,partial.id,untouched.id,failed.id]);
  const card=(id:string)=>page.locator('[data-model-id="'+id+'"]').locator("..");
  await expect(card(passed.id)).toContainText("测试已通过");
  await expect(card(partial.id)).toContainText("部分测试通过");
  await expect(card(partial.id)).toContainText("文本已连通");
  await expect(card(partial.id)).toContainText("图片未测试");
  await expect(card(failed.id)).toContainText("文本未连通");
  await expect(card(untouched.id)).toContainText("尚未测试");
  await page.reload();
  await expect(card(passed.id)).toContainText("文本已连通");
  await page.locator('[data-model-id="'+passed.id+'"]').evaluate(el=>el.scrollIntoView({block:"start"}));
  await page.screenshot({path:artifactPath("model-connection-order.png"),fullPage:false});
  await page.setViewportSize({width:375,height:812});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  const axe=await new AxeBuilder({page}).withTags(["wcag2a","wcag2aa","wcag21aa"]).analyze();
  expect(axe.violations).toEqual([]);
  await page.screenshot({path:artifactPath("model-connection-mobile.png"),fullPage:false});
  const changed=await request.put("/v1/settings/models/"+passed.id,{data:{name:passed.name,base_url:passed.base_url,model_name:"changed-model-id",api_key:null,supports_vision:false,allow_external_egress:true}});
  expect(changed.ok()).toBeTruthy();
  await page.reload();
  await expect(card(passed.id)).toContainText("尚未测试");
  await expect(card(passed.id)).not.toContainText("文本已连通");
});
