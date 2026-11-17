import { test,expect,artifactPath } from './fixtures';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
test('history shows saved unscored trials without requiring a formal release',async({page,request})=>{
 const data=process.env.E2E_DATA_DIR!;expect(path.resolve(data)).toContain(path.resolve('../.tools/e2e-data'));
 const fid='history-'+crypto.randomUUID();
 const script=[
 "import sys; from screenshotlegal.research.store import Store; from screenshotlegal.research.contracts import now",
 "s=Store(sys.argv[1]); fid=sys.argv[2]",
 "with s.tx() as db:",
 " s.put('research.flow',dict(id=fid,name='Saved QA trial',status='awaiting_human_review',created_at=now(),summary=dict(qa_requests=2,qa_success=2,qa_by_mode={'text':1,'multi_image':1}),steps=[dict(stage='Question answering',result='Two saved responses; unscored')],artifacts=[]),'e2eadmin',db,immutable=True)",
 " s.put('evaluation.probe',dict(id='probe-'+fid,scope='development_qa',flow_id=fid,success=True,mode='text',created_at=now(),response={'raw':'Saved answer'}),'e2eadmin',db,immutable=True)"
 ].join('\n');
 execFileSync(path.resolve('../.conda/screenshotlegal-v1',process.platform==='win32'?'python.exe':'bin/python'),['-X','utf8','-c',script,data,fid],{cwd:path.resolve('..'),windowsHide:true});
 await page.goto('/evaluation.html');await page.getByText('全部运行历史（含旧试跑）',{exact:true}).click();const table=page.getByRole('table',{name:'评测与试跑运行历史',exact:true});
 const row=table.getByRole('row').filter({hasText:'Saved QA trial'});await expect(row).toContainText('未计分试跑');await expect(row).toContainText('已返回 2 / 2');await expect(row.getByRole('link',{name:'查看试跑结果 →',exact:true})).toHaveAttribute('href',/record=history-/);
 await page.getByRole('combobox',{name:'运行记录类型',exact:true}).selectOption('formal');await expect(table).not.toContainText('Saved QA trial');await expect(page.getByText('尚无正式评测。已有试跑请切换“全部记录”或“未计分试跑”；完成审核并发布后可创建正式评测。',{exact:true})).toBeVisible();
 await page.getByRole('combobox',{name:'运行记录类型',exact:true}).selectOption('trial');await expect(row).toBeVisible();await page.screenshot({path:artifactPath('evaluation-history.png'),fullPage:true});
 await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();await page.screenshot({path:artifactPath('evaluation-history-mobile.png'),fullPage:true});
 await row.getByRole('link',{name:'查看试跑结果 →',exact:true}).click();await expect(page.getByRole('heading',{name:'过程与结果详情',exact:true})).toBeVisible();await expect(page.getByRole('listitem').filter({hasText:'Two saved responses; unscored'})).toBeVisible();
 expect(await(await request.get('/v1/evaluation/runs')).json()).toEqual([]);
});
