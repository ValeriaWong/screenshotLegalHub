import { test,expect,artifactPath } from './fixtures';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
const id=()=>crypto.randomUUID();
test('configured waits, explicit image scope and per-call audit work together',async({page,request})=>{
 const model=await(await request.post('/v1/settings/models',{data:{name:'Scope model '+id(),base_url:'http://127.0.0.1:19432/v1',model_name:'scope',api_key:'e2e-placeholder',allow_external_egress:true,supports_vision:true}})).json();
 await page.goto('/evaluation.html?models=1');await page.locator('section.card').filter({has:page.getByRole('heading',{name:new RegExp('^'+model.name)})}).getByRole('button',{name:'编辑模型',exact:true}).click();
 await expect(page.getByLabel('无响应等待时间（秒）',{exact:true})).not.toBeVisible();await page.getByText('高级：等待模型的时间',{exact:true}).click();await page.getByLabel('无响应等待时间（秒）',{exact:true}).fill('7');await page.getByLabel('单次调用总时长（秒，可选）',{exact:true}).fill('30');await page.getByRole('button',{name:'保存',exact:true}).click();
 await expect.poll(async()=>((await(await request.get('/v1/settings/models')).json()).find((m:any)=>m.id===model.id)).request_timeout_seconds).toBe(7);
 const source=await(await request.post('/v1/review/samples',{data:{dataset:'scope-test',content:{title:'English reading with complete identity and time',language:'en',platform:'WhatsApp',source_text:'Synthetic fixture, not evidence.',messages:[{id:'m1',speaker:'Source sender with a deliberately long identity label',timestamp:'2026-10-24 10:49',text:'Srimila says it leaves everything to amma before she replies.'}]},note:'scope fixture',idempotency_key:id()}})).json();const sid=source.sample.id;
 await expect.poll(async()=>(await(await request.get('/v1/review/samples/'+sid)).json()).binding?.manifest_id||'',{timeout:20000}).not.toBe('');
 const rule=await(await request.post('/v1/review/prompts',{data:{name:'scope-rule-'+id(),markdown:'# Check only the reviewed manifest',note:'fixture',expected_version:0,idempotency_key:id()}})).json();
 await page.goto('/review.html?sample='+sid);await page.getByText('需要模型协助检查？',{exact:true}).click();await page.getByRole('combobox',{name:'模型评估范围',exact:true}).selectOption('multimodal');await page.getByRole('combobox',{name:'检查规则',exact:true}).selectOption(rule.id);await page.getByRole('combobox',{name:'评估模型',exact:true}).selectOption(model.id);await page.getByRole('button',{name:'提交质量评估任务',exact:true}).click();
 await expect.poll(async()=>(await(await request.get('/v1/review/samples/'+sid)).json()).quality.filter((q:any)=>q.method==='model').length,{timeout:20000}).toBe(1);
 const detail=await(await request.get('/v1/review/samples/'+sid)).json();const q=detail.quality.find((q:any)=>q.method==='model');expect(q.reviewed_object.expected_pages).toBe(1);expect(q.reviewed_object.visual_role).toBe('synthetic_render');expect(q.input_contract_version).toBe('quality-input.v2');expect(q.model_snapshot.timeout_policy.read).toBe(7);expect(q.model_snapshot.timeout_policy.total).toBe(30);
 const rid=q.response.request_id;const logs=await(await request.get('/v1/research/audit-events?request_id='+rid)).json();expect(logs.items.filter((e:any)=>e.object_type==='evaluation.request')).toHaveLength(2);expect(logs.items.every((e:any)=>e.context.model_call_id===rid)).toBe(true);const summary=await(await request.get('/v1/research/audit-summary?request_id='+rid)).json();expect(summary.total).toBe(logs.items.length);
 await page.goto('/review.html?audit=1&request_id='+rid);const row=page.getByRole('row').filter({hasText:'evaluation.request.updated'});await expect(row).toBeVisible();await row.getByRole('button',{name:'查看这次操作',exact:true}).click();const dialog=page.getByRole('dialog',{name:'操作审计详情',exact:true});await dialog.getByText('调用编号与记录位置',{exact:true}).click();await expect(dialog).toContainText('模型调用：'+rid);await expect(dialog).toContainText('mock-provider-'+rid);await page.screenshot({path:artifactPath('call-audit.png'),fullPage:true});
 // This fixture is restricted to the fresh E2E database; it never rewrites production history.
 const data=process.env.E2E_DATA_DIR!;expect(path.resolve(data)).toContain(path.resolve('../.tools/e2e-data'));
 const script="import json,sys; from screenshotlegal.research.store import Store; s=Store(sys.argv[1]); q=json.loads(sys.argv[2]); q['id']='legacy-'+q['id']; q.pop('input_contract_version',None); q.pop('reviewed_object',None); q['protocol_id']='legacy-fixture'; q['findings']='Legacy fixture'; db=s.tx(); c=db.__enter__(); s.put('review.quality',q,'e2eadmin',c,immutable=True); db.__exit__(None,None,None)";
 execFileSync(path.resolve('../.conda/screenshotlegal-v1',process.platform==='win32'?'python.exe':'bin/python'),['-c',script,data,JSON.stringify(q)],{cwd:path.resolve('..'),windowsHide:true});await page.goto('/review.html?sample='+sid);await expect(page.getByText('部分历史模型意见的图片范围需要复核。请先核对实际图片清单，再采纳补图或缺页建议。')).toBeVisible();await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();await page.screenshot({path:artifactPath('review-scope-mobile.png'),fullPage:true});
});

test('legacy layout upgrade keeps text and protects comment drafts',async({page,request})=>{
 const data=process.env.E2E_DATA_DIR!;expect(path.resolve(data)).toContain(path.resolve('../.tools/e2e-data'));
 const script=[
 'import json,sys',
 'from screenshotlegal.research.store import Store',
 'from screenshotlegal.research.review import ReviewDesk',
 'from screenshotlegal.research.contracts import SampleCreate,dumps',
 's=Store(sys.argv[1]);r=ReviewDesk(s)',
 'with s.tx() as db:',
 " result=r.create('e2eadmin',SampleCreate(dataset='legacy-upgrade-fixture',content=dict(title='Legacy layout fixture',language='en',messages=[dict(id='m1',speaker='Long identity',timestamp='10:49',text='Read this before replying; it leaves the amount unchanged.')]),note='Isolated legacy fixture',idempotency_key='legacy-fixture'),db=db)",
 " revision=result['revision'];revision['renderer_version']='pillow-chat.v3'",
 ' db.execute("UPDATE records SET body=? WHERE kind=\'review.revision\' AND id=?",(dumps(revision),revision[\'id\']))',
 " job=s.job(result['job_id'],'e2eadmin',db);job['payload']['revision']=revision;s.save_job(db,job)",
 "print(json.dumps(result['sample']))"].join('\n');
 const sample=JSON.parse(execFileSync(path.resolve('../.conda/screenshotlegal-v1',process.platform==='win32'?'python.exe':'bin/python'),['-c',script,data],{cwd:path.resolve('..'),windowsHide:true}).toString());const sid=sample.id;
 await expect.poll(async()=>(await(await request.get('/v1/review/samples/'+sid)).json()).binding?.manifest_id||'',{timeout:20000}).not.toBe('');
 const before=await(await request.get('/v1/review/samples/'+sid)).json();const old=before.sample.published_manifest;
 await page.goto('/review.html?sample='+sid);const upgrade=page.getByRole('button',{name:'按新版排版生成新版本',exact:true});await expect(upgrade).toBeEnabled();
 await page.getByText('添加样本评论 / 查看评论（0）',{exact:true}).click();await page.getByLabel('审核评论',{exact:true}).fill('Keep my unsaved comment');await expect(upgrade).toBeDisabled();await page.getByLabel('审核评论',{exact:true}).fill('');await expect(upgrade).toBeEnabled();await upgrade.click();
 await expect.poll(async()=>(await(await request.get('/v1/review/samples/'+sid)).json()).revision.number).toBe(2);
 await expect.poll(async()=>(await(await request.get('/v1/review/samples/'+sid)).json()).binding?.revision||0,{timeout:20000}).toBe(2);
 const after=await(await request.get('/v1/review/samples/'+sid)).json();expect(after.revision.content).toEqual(before.revision.content);expect(after.revision.renderer_version).toBe('pillow-chat.v4');expect(after.sample.status).toBe('needs_review');expect(after.sample.published_manifest).not.toBe(old);expect((await request.get('/v1/review/manifests/'+old)).ok()).toBeTruthy();await expect(upgrade).not.toBeVisible();await page.screenshot({path:artifactPath('explicit-layout-upgrade.png'),fullPage:true});
});

test('operations explains local software verification without model claims',async({page})=>{
 const data=process.env.E2E_DATA_DIR!;expect(path.resolve(data)).toContain(path.resolve('../.tools/e2e-data'));
 const fid='software-fixture-'+id();
 const script="import json,sys; from screenshotlegal.research.store import Store; s=Store(sys.argv[1]); row=json.loads(sys.argv[2]); db=s.tx(); c=db.__enter__(); s.put('research.flow',row,'e2eadmin',c,immutable=True); db.__exit__(None,None,None)";
 const row={id:fid,flow_id:fid,name:'Software verification fixture',status:'completed',created_at:new Date().toISOString(),summary:{flow_type:'software_verification',real_model_calls:0,verification:{backend:1,frontend_unit:2,browser:3}},steps:[{stage:'Fixture stage',result:'Fixture result'}],artifacts:[]};
 execFileSync(path.resolve('../.conda/screenshotlegal-v1',process.platform==='win32'?'python.exe':'bin/python'),['-c',script,data,JSON.stringify(row)],{cwd:path.resolve('..'),windowsHide:true});
 await page.goto('/evaluation.html?operations=1&kind=research.flow&record='+fid);await expect(page.getByRole('heading',{name:'软件验证已完成',exact:true})).toBeVisible();await expect(page.getByText('本轮展示本地回归和模拟服务的测试结果。真实模型调用 0 次；不产生新的模型质量结论。',{exact:true})).toBeVisible();await expect(page.getByLabel('本轮软件验证',{exact:true})).toContainText('浏览器场景通过');await expect(page.getByLabel('本轮关键进度',{exact:true})).not.toBeVisible();await expect(page.getByRole('listitem').filter({hasText:'Fixture stage：Fixture result'})).toBeVisible();await page.screenshot({path:artifactPath('software-verification-flow.png'),fullPage:true});
});
