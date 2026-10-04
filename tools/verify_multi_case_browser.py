"""Exercise our own local app in an isolated headless Edge profile."""
import base64
import argparse
import json
import subprocess
import sys
import time
import uuid
from pathlib import Path
import requests
import websocket
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from legalhub import benchmark as b

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--resume',action='store_true');parser.add_argument('--completed-upload',action='store_true');args=parser.parse_args()
    edge=Path('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe')
    profile=b.ROOT/'tmp'/('multi-case-browser-'+uuid.uuid4().hex[:8]);profile.mkdir(parents=True)
    process=subprocess.Popen([str(edge),'--headless=new','--no-sandbox','--disable-gpu','--no-first-run',
        '--remote-debugging-port=9225','--remote-debugging-address=127.0.0.1','--remote-allow-origins=http://localhost:9225',
        '--user-data-dir='+str(profile),'--window-size=1440,1050','http://127.0.0.1:18420/'],
        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
    ws=None;serial=0;session=requests.Session();session.trust_env=False
    try:
        deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            try:
                tabs=session.get('http://127.0.0.1:9225/json',timeout=1).json()
                tab=next(t for t in tabs if t.get('type')=='page' and t['url'].startswith('http://127.0.0.1:18420'))
                break
            except (requests.RequestException,StopIteration):time.sleep(.2)
        else:raise RuntimeError('Isolated browser did not start; process exit='+str(process.poll()))
        ws=websocket.create_connection(tab['webSocketDebuggerUrl'],origin='http://localhost:9225',timeout=10)
        def command(method,params=None):
            nonlocal serial
            serial+=1;ws.send(json.dumps({'id':serial,'method':method,'params':params or {}}))
            while True:
                row=json.loads(ws.recv())
                if row.get('id')==serial:
                    if 'error' in row:raise RuntimeError(row['error'])
                    return row['result']
        def evaluate(expression):
            result=command('Runtime.evaluate',{'expression':expression,'returnByValue':True,'awaitPromise':True})
            if result.get('exceptionDetails'):raise RuntimeError(result['exceptionDetails'])
            return result['result'].get('value')
        def until(expression,seconds=15):
            stop=time.monotonic()+seconds
            while time.monotonic()<stop:
                if evaluate(expression):return
                time.sleep(.1)
            raise AssertionError(expression)
        command('Runtime.enable')
        until("document.querySelectorAll('.case-tile').length===24")
        def shot(name):
            row=command('Page.captureScreenshot',{'format':'png','captureBeyondViewport':False})
            output=b.ROOT/'reports'/name;output.write_bytes(base64.b64decode(row['data']))
            return output.relative_to(b.ROOT).as_posix()
        until("document.querySelector('.case-tile img').complete && document.querySelector('.case-tile img').naturalWidth>0")
        count=evaluate("cases.length");assert count>=315
        assert evaluate("cases.reduce((n,c)=>n+c.images,0)")>=1172
        overview=shot('v1.1.0_cases_desktop.png')
        evaluate("document.querySelector('#case-query').value='58b7dff082ec3972eb9edeb4';document.querySelector('#case-query').dispatchEvent(new Event('input'))")
        assert evaluate("document.querySelectorAll('.case-tile').length")==1
        assert evaluate("document.querySelector('.tile-status').textContent")=='已有转录'
        evaluate("document.querySelector('#case-query').value='';document.querySelector('#case-query').dispatchEvent(new Event('input'));document.querySelector('#next-page').click()")
        assert evaluate("page")==1
        evaluate("document.querySelector('#language').value='en';document.querySelector('#language').dispatchEvent(new Event('change'))")
        assert 'Every finding' in evaluate("document.querySelector('#hero-title').textContent")
        command('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
        assert evaluate("document.documentElement.scrollWidth<=window.innerWidth"),'Case library mobile overflow'
        evaluate("window.scrollTo({top:0,behavior:'instant'})")
        mobile_hub=shot('v1.1.0_cases_mobile.png')
        command('Emulation.clearDeviceMetricsOverride')
        if not args.resume:
            evaluate("document.querySelector('#language').value='zh';document.querySelector('#language').dispatchEvent(new Event('change'));document.querySelector('#new-case').click()")
            node=command('DOM.getDocument')['root']['nodeId']
            file_input=command('DOM.querySelector',{'nodeId':node,'selector':'#case-files'})['nodeId']
            paths=[str(b.ROOT/'projects/ScreenshotLegalBench_v2/process_local_evaluator/images'/('5ad6f87311be1056f7197a9f_image_'+str(n)+'.jpg')) for n in (5,6)]
            command('DOM.setFileInputFiles',{'nodeId':file_input,'files':paths})
            until("document.querySelectorAll('.upload-preview').length===2")
            evaluate("document.querySelector('#case-name').value='上传流程验收 · 衣服付款';document.querySelector('#case-context').value='本次用两张现有原图验证上传流程，身份和实际支付尚未核实。'")
            intake=shot('v1.1.0_upload_intake.png')
            evaluate("document.querySelector('#create-form').requestSubmit()")
            until("location.pathname==='/case' && typeof state!=='undefined' && state?.images.length===2",60)
            uploaded=evaluate("caseId")
            assert uploaded.startswith('case-')
            assert evaluate("!document.querySelector('#case-generation-banner').hidden")
            assert evaluate("document.querySelector('#user-context-text').textContent.includes('尚未核实')")
            generation=shot('v1.1.0_upload_generation.png')
            b.write(b.ROOT/'reports/v1.1.0_uploaded_test_case.json',{'case_id':uploaded,'name':'上传流程验收 · 衣服付款','images':2,'source_files':paths,'actual_model_generation_requested':True})
            print(json.dumps({'created_case':uploaded,'actual_generation':True}),flush=True)
        else:
            uploaded=b.read(b.ROOT/'reports/v1.1.0_uploaded_test_case.json')['case_id']
            intake='reports/v1.1.0_upload_intake.png';generation='reports/v1.1.0_upload_generation.png'
        command('Page.navigate',{'url':'http://127.0.0.1:18420/case?case_id=5ad6f87311be1056f7197a9f'})
        until("typeof state!=='undefined' && state?.case_id==='5ad6f87311be1056f7197a9f' && document.querySelectorAll('.timeline-section').length===6")
        evaluate("document.querySelector('#language').value='zh';document.querySelector('#language').dispatchEvent(new Event('change'));document.querySelector('[data-mode=qa]').click()")
        until("!document.querySelector('#qa-view').hidden && document.querySelectorAll('#qa-model option').length>=3")
        assert evaluate("document.querySelector('#timeline').hidden")
        if not args.resume:
            evaluate("document.querySelector('#qa-model').value='fast';document.querySelector('#qa-question').value='现有聊天中有什么转账线索？能否确认原告本人实际转账？';document.querySelector('#qa-form').requestSubmit()")
            until("document.querySelector('.qa-waiting')!==null",15)
            until("document.querySelector('.inline-citation')!==null || document.querySelector('.qa-error')!==null",170)
        else:
            until("document.querySelector('.inline-citation')!==null",30)
        assert evaluate("document.querySelector('.qa-error')===null"),evaluate("document.querySelector('.qa-error')?.textContent")
        assert evaluate("document.querySelectorAll('.inline-citation').length")>0
        assert evaluate("document.querySelector('.qa-verdict').textContent")=='证据不足'
        answer=shot('v1.1.0_case_qa.png')
        box=evaluate("(()=>{const n=document.querySelector('.inline-citation');n.scrollIntoView({block:'center',behavior:'instant'});const r=n.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()")
        command('Input.dispatchMouseEvent',{'type':'mousePressed','x':box['x'],'y':box['y'],'button':'left','clickCount':1})
        command('Input.dispatchMouseEvent',{'type':'mouseReleased','x':box['x'],'y':box['y'],'button':'left','clickCount':1})
        until("!document.querySelector('#citation-drawer').hidden")
        until("document.querySelector('.citation-stage img').complete && document.querySelector('.citation-stage img').naturalWidth>0")
        assert evaluate("document.querySelector('.citation-stage rect')!==null")
        assert evaluate("document.querySelector('#citation-drawer').getBoundingClientRect().right<=window.innerWidth+1")
        assert evaluate("document.querySelector('.citation-quote').textContent.includes('支付宝')||document.querySelector('.citation-quote').textContent.includes('2000')||document.querySelector('.citation-quote').textContent.includes('手下')")
        citation=shot('v1.1.0_case_qa_citation.png')
        command('Input.dispatchKeyEvent',{'type':'keyDown','key':'Escape','code':'Escape','windowsVirtualKeyCode':27})
        until("document.querySelector('#citation-drawer').hidden")
        command('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
        assert evaluate("document.documentElement.scrollWidth<=window.innerWidth"),'Case Q&A mobile overflow'
        evaluate("document.querySelector('.inline-citation').click()")
        until("!document.querySelector('#citation-drawer').hidden")
        mobile_qa=shot('v1.1.0_qa_mobile.png')
        command('Emulation.clearDeviceMetricsOverride')
        command('Page.navigate',{'url':'http://127.0.0.1:18420/case?case_id=58b7dff082ec3972eb9edeb4'})
        until("typeof state!=='undefined' && state?.case_id==='58b7dff082ec3972eb9edeb4' && document.querySelectorAll('.timeline-section').length===3")
        assert evaluate("document.querySelector('#case-generation-banner').hidden===false")
        assert evaluate("document.querySelectorAll('.legal-event-card').length")==0
        assert evaluate("Array.from(document.querySelectorAll('.process-step span')).every(n=>n.textContent==='尚待分析')")
        evaluate("document.querySelector('[data-mode=qa]').click()")
        until("document.querySelector('#qa-model option')!==null")
        assert evaluate("document.querySelector('.qa-claim')===null"),'Q&A leaked across cases'
        completion=None
        if args.completed_upload:
            command('Page.navigate',{'url':'http://127.0.0.1:18420/case?case_id='+uploaded})
            until("typeof state!=='undefined' && state?.case_id==="+json.dumps(uploaded)+" && state.analysis && graph.contract_terms.length===8",30)
            assert evaluate("state.job.status==='completed' && state.job.vision_complete===true")
            assert evaluate("state.quality.images_ok===2 && state.message_count===19")
            assert evaluate("document.querySelectorAll('.timeline-section').length===2")
            assert evaluate("graph.conversations.length===1 && L(graph.conversations[0].name).includes('公瑾')")
            until("Array.from(document.querySelectorAll('.source-stage img')).every(n=>n.complete && n.naturalWidth>0)")
            complete_shot=shot('v1.1.0_uploaded_case_complete.png')
            assert evaluate("state.analysis.request_proof.http_status===200 && !!state.analysis.request_proof.response_id")
            assert evaluate("graph.legal_events.length>0")
            evaluate("document.querySelector('[data-mode=contract]').click()")
            assert evaluate("document.querySelectorAll('#contract-view tbody tr').length===8")
            evaluate("document.querySelector('#contract-view').scrollIntoView({block:'start',behavior:'instant'})")
            contract_shot=shot('v1.1.0_uploaded_contract.png')
            evaluate("document.querySelector('#contract-view tr[data-term=payment] button').click()")
            until("!document.querySelector('#inspection').hidden")
            assert evaluate("document.querySelector('#inspection-source img')!==null")
            completion={'status':'completed','images_read':2,'messages':19,'model_http_status':200,'run_id':evaluate('state.analysis.run_id'),'contract_terms':8,'terms_link_to_original':True,'screenshots':[complete_shot,contract_shot]}
        result={'registered_cases_at_check':count,'existing_case_groups':315,'library_pagination':True,'case_filtering':True,'i18n':True,'multi_image_upload':uploaded,
                'actual_upload_generation_requested':True,'actual_qa_request':True,'identity_question_kept_uncertain':True,'numbered_inline_citations':True,
                'right_citation_drawer':True,'original_bbox_shown':True,'escape_close':True,'chat_case_isolation':True,'mobile_overflow':False,
                'unanalysed_legal_stages_honest':True,'completed_uploaded_case':completion,'screenshots':[overview,mobile_hub,intake,generation,answer,citation,mobile_qa]}
        b.write(b.ROOT/'reports/v1.1.0_multi_case_browser.json',result);print(json.dumps(result,ensure_ascii=True))
        command('Browser.close')
    finally:
        if ws:ws.close()
        try:process.wait(timeout=5)
        except subprocess.TimeoutExpired:process.terminate()
if __name__=='__main__':main()
