"""Exercise our own local app in an isolated headless Edge profile."""
import base64
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
    edge=Path('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe')
    profile=b.ROOT/'tmp'/('one-case-browser-'+uuid.uuid4().hex[:8]);profile.mkdir(parents=True)
    process=subprocess.Popen([str(edge),'--headless=new','--no-sandbox','--disable-gpu','--no-first-run',
        '--remote-debugging-port=9224','--remote-debugging-address=127.0.0.1','--remote-allow-origins=http://localhost:9224',
        '--user-data-dir='+str(profile),'--window-size=1440,1050','http://127.0.0.1:18420/case?case_id=5ad6f87311be1056f7197a9f'],
        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
    ws=None;serial=0;session=requests.Session();session.trust_env=False
    try:
        deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            try:
                tabs=session.get('http://127.0.0.1:9224/json',timeout=1).json()
                tab=next(t for t in tabs if t.get('type')=='page' and t['url'].startswith('http://127.0.0.1:18420'))
                break
            except (requests.RequestException,StopIteration):time.sleep(.2)
        else:raise RuntimeError('Isolated browser did not start; process exit='+str(process.poll()))
        ws=websocket.create_connection(tab['webSocketDebuggerUrl'],origin='http://localhost:9224',timeout=10)
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
        def until(expression):
            stop=time.monotonic()+10
            while time.monotonic()<stop:
                if evaluate(expression):return
                time.sleep(.1)
            raise AssertionError(expression)
        command('Runtime.enable')
        until("document.querySelectorAll('.timeline-section').length===6")
        until("document.querySelector('.source-panel img').complete && document.querySelector('.source-panel img').naturalWidth>0")
        assert evaluate("document.querySelector('[data-mode=conversation]').getAttribute('aria-pressed')")== 'true'
        initial={'sections':evaluate("document.querySelectorAll('.timeline-section').length"),
                 'source_images':evaluate("document.querySelectorAll('#timeline .source-panel img').length"),
                 'meaning_cards':evaluate("document.querySelectorAll('#timeline .meaning-card').length"),
                 'conversation_name':evaluate("document.querySelector('.conversation-heading strong').textContent"),
                 'legal_nodes':evaluate("document.querySelectorAll('#milestone-nav button').length")}
        assert '公瑾' in initial['conversation_name']
        assert initial['legal_nodes']==8
        assert evaluate("document.querySelectorAll('#conversation-nav button').length")==2
        assert evaluate("graph.legal_events.every(e=>!['withdrawal','revocation','counteroffer'].includes(e.type))")
        def shot(name):
            row=command('Page.captureScreenshot',{'format':'png','captureBeyondViewport':False})
            output=b.ROOT/'reports'/name;output.write_bytes(base64.b64decode(row['data']))
            return output.relative_to(b.ROOT).as_posix()
        overview=shot('v1.0.0_case_legal_workspace_desktop.png')
        # Actual pointer input against an original-image message rectangle.
        evaluate("window.receipt=state.messages.find(m=>m.text==='收到了'); document.querySelectorAll('#timeline .source-panel')[5].scrollIntoView({block:'start',behavior:'instant'})")
        until("document.querySelectorAll('#timeline .source-panel img')[5].complete")
        box=evaluate("(()=>{const r=Array.from(document.querySelectorAll('#timeline rect.message-hit')).find(n=>n.dataset.message===receipt.id);r.scrollIntoView({block:'center',behavior:'instant'});const b=r.getBoundingClientRect();return {x:b.x+b.width/2,y:b.y+b.height/2};})()")
        command('Input.dispatchMouseEvent',{'type':'mousePressed','x':box['x'],'y':box['y'],'button':'left','clickCount':1})
        command('Input.dispatchMouseEvent',{'type':'mouseReleased','x':box['x'],'y':box['y'],'button':'left','clickCount':1})
        until("!document.querySelector('#inspection').hidden && document.querySelector('#timeline').hidden")
        until("document.querySelector('#inspection-content .meaning-card.selected')?.textContent.includes('收款确认')")
        until("document.querySelector('#inspection-source img').complete")
        assert evaluate("document.querySelector('#inspection-source rect.message-hit.selected').dataset.message===receipt.id")
        assert evaluate("document.querySelector('#inspection-source .source-context')===null")
        def horizontal():
            return evaluate("(()=>{const a=document.querySelector('#inspection-source').getBoundingClientRect(),b=document.querySelector('.inspection-right').getBoundingClientRect();return {left:a.x,left_right:a.right,right:b.x,right_width:b.width,source_width:a.width,horizontal:a.right<=b.x+2 && Math.abs(a.top-b.top)<3};})()")
        layout=horizontal();assert layout['horizontal'],layout
        reverse={'selected_meaning':evaluate("document.querySelector('#inspection-content .meaning-card.selected h3').textContent"),'layout':layout}
        inspection=shot('v1.0.0_case_legal_workspace_inspection.png')
        evaluate("document.querySelector('[data-inspect=context]').click()")
        assert evaluate("document.querySelector('#inspection-content .selection-context').textContent.includes('钱收到没')")
        assert evaluate("document.querySelector('#inspection-source .selection-context')===null")
        # Follow a supporting quote to another image, then inspect its legal meaning.
        evaluate("document.querySelector('[data-legal-event=\"'+graph.legal_events.find(e=>e.type==='performance_notice').id+'\"]').click()")
        evaluate("Array.from(document.querySelectorAll('#inspection-content .quote')).find(n=>n.textContent.includes('支付宝发给我')).click()")
        until("document.querySelector('#inspection-source rect.message-hit.selected')?.getAttribute('aria-label').includes('支付宝发给我')")
        assert evaluate("document.querySelector('#inspection-source .source-panel').dataset.source===state.messages.find(m=>m.text==='支付宝发给我').image_id")
        assert evaluate("document.querySelector('#inspection-content .meaning-card')!==null")
        forward={'selected_original':evaluate("document.querySelector('#inspection-source rect.message-hit.selected').getAttribute('aria-label')"),
                 'page':evaluate("document.querySelector('#inspection-source .panel-label strong').textContent")}
        evaluate("document.querySelector('#back-timeline').click();document.querySelector('[data-mode=legal]').click()")
        until("document.querySelectorAll('.timeline-section').length===8")
        assert evaluate("Array.from(document.querySelectorAll('#timeline .legal-event-card')).some(n=>n.textContent.includes('要约审查')&&n.textContent.includes('待核实'))")
        assert evaluate("graph.legal_events.every(e=>e.source_refs.length>0)")
        evaluate("document.querySelector('[data-mode=contract]').click();document.querySelector('#contract-view').scrollIntoView({block:'start',behavior:'instant'})")
        until("document.querySelectorAll('#contract-view tbody tr').length===8")
        assert evaluate("document.querySelector('#contract-view tr[data-term=price]').textContent.includes('待核实')")
        assert evaluate("graph.contract_terms.find(t=>t.key==='delivery').source_refs.length===0")
        contract=shot('v1.0.0_case_legal_workspace_contract.png')
        evaluate("document.querySelector('#contract-view tr[data-term=price] button').click()")
        assert horizontal()['horizontal']
        assert evaluate("document.querySelector('#inspection-content .term-card').dataset.term==='price'")
        # Language switching preserves the selection. Raw evidence stays verbatim.
        evaluate("document.querySelector('#language').value='en';document.querySelector('#language').dispatchEvent(new Event('change'))")
        assert evaluate("document.documentElement.lang")=='en'
        assert evaluate("document.querySelector('#case-title').textContent").startswith('Clothing')
        assert evaluate("document.querySelector('[data-mode=contract]').textContent")=='Contract terms'
        assert not evaluate("/[\\u4e00-\\u9fff]/.test(document.querySelector('#inspection-content .term-card h3').textContent)")
        assert evaluate("Array.from(document.querySelectorAll('#inspection-content .quote')).some(n=>n.textContent.includes('多少钱'))")
        english=shot('v1.0.0_case_legal_workspace_en.png')
        command('Page.reload')
        until("document.querySelectorAll('.timeline-section').length===6")
        assert evaluate("document.querySelector('#language').value")=='en'
        assert evaluate("document.querySelector('#case-title').textContent").startswith('Clothing')
        evaluate("document.querySelector('#query').value='receipt confirmation';document.querySelector('#search-form').dispatchEvent(new Event('submit',{cancelable:true}))")
        until("document.querySelector('#search-status').textContent.includes('matches')")
        assert evaluate("document.querySelectorAll('#search-results button').length")>0
        search=evaluate("document.querySelector('#search-status').textContent")
        evaluate("document.querySelector('#search-results button').click()")
        assert not evaluate("/[\\u4e00-\\u9fff]/.test(Array.from(document.querySelectorAll('#inspection-content .meaning-card .card-field')).map(n=>n.textContent).join(' '))")
        # Keep the inspector in two columns even on a narrow viewport.
        command('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
        until("window.innerWidth===390")
        evaluate("document.querySelector('#inspection').scrollIntoView({block:'start',behavior:'instant'})")
        assert evaluate("document.documentElement.scrollWidth<=window.innerWidth"),'Mobile layout overflow'
        mobile_layout=horizontal();assert mobile_layout['horizontal'],mobile_layout
        until("document.querySelector('#inspection-source img').complete")
        mobile=shot('v1.0.0_case_legal_workspace_mobile.png')
        command('Emulation.clearDeviceMetricsOverride')
        evaluate("document.querySelector('#back-timeline').click();document.querySelector('#details-toggle').click()")
        assert 'Qwen/Qwen3.8-27B' in evaluate("document.querySelector('#model-status').textContent")
        assert 'Source-reviewed' in evaluate("document.querySelector('#analysis-origin').textContent")
        assert not evaluate("/[\\u4e00-\\u9fff]/.test(document.querySelector('#review-list').textContent)")
        assert evaluate("!document.querySelector('#case-details').hidden")
        # Explicit synthetic two-conversation fixture; never persisted as case evidence.
        evaluate("window.realGraph=graph;graph=structuredClone(graph);graph.conversations=[{id:'test-a',name:{zh:'验证会话 A',en:'Test conversation A'},image_ids:state.images.slice(0,5).map(x=>x.image_id)},{id:'test-b',name:{zh:'验证会话 B',en:'Test conversation B'},image_ids:[state.images[5].image_id]}];for(const c of graph.conversations)for(const id of c.image_ids)graph.image_conversations[id]=c.id;for(const p of graph.pages)p.conversation_id=graph.image_conversations[p.image_id];for(const e of graph.legal_events)e.conversation_ids=[...new Set(e.image_ids.map(id=>graph.image_conversations[id]))];indices();paintState();chooseChat('all');")
        assert evaluate("document.querySelectorAll('.conversation-heading').length")==2
        assert evaluate("document.querySelectorAll('#conversation-nav button').length")==3
        evaluate("document.querySelector('[data-conversation=test-b]').click()")
        assert evaluate("document.querySelectorAll('.timeline-section').length")==1
        assert evaluate("document.querySelector('.conversation-heading strong').textContent")=='Test conversation B'
        evaluate("document.querySelector('[data-mode=legal]').click();document.querySelector('[data-legal-event=\"'+graph.legal_events.find(e=>e.type==='performance_notice').id+'\"]').click()")
        assert evaluate("document.querySelector('#inspection-meta').textContent.includes('Test conversation A')&&document.querySelector('#inspection-meta').textContent.includes('Test conversation B')")
        assert evaluate("document.querySelectorAll('#inspection-source .source-panel').length")>=2
        assert horizontal()['horizontal']
        evaluate("graph=realGraph;chat='all';mode='conversation';selection=null;indices();paintState();paintNav();renderTimeline()")
        result={'initial':initial,'original_to_meaning':reverse,'meaning_to_original':forward,
                'legal_sections':8,'terms':8,'context_on_right_only':True,'unseen_legal_stages_not_fabricated':True,
                'english_persisted':True,'raw_evidence_preserved':True,'english_search':search,
                'mobile_overflow':False,'mobile_inspector':mobile_layout,
                'screenshots':[overview,inspection,contract,english,mobile],'browser_profile':'isolated_headless_test',
                'model_button_clicked':False,'two_conversation_fixture':{'names_visible':True,'filter_isolates_conversation':True,'cross_conversation_evidence_keeps_both_names':True,'persisted_as_case_evidence':False}}
        b.write(b.ROOT/'reports/v1.0.0_case_legal_workspace_browser.json',result);print(json.dumps(result,ensure_ascii=True))
        command('Browser.close')
    finally:
        if ws:ws.close()
        try:process.wait(timeout=5)
        except subprocess.TimeoutExpired:process.terminate()
if __name__=='__main__':main()
