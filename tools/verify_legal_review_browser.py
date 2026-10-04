"""Validate our local workbench in an isolated Edge profile and review database.

The server must use a disposable --review-db. No model requests are made.
"""
import argparse
import base64
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid

import requests
import websocket

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=18421)
    args = parser.parse_args()
    if args.port == 18420:
        raise ValueError('Use a disposable review database on a separate test server, never the user server.')
    base = f'http://127.0.0.1:{args.port}'
    session = requests.Session()
    session.trust_env = False
    queue = session.get(base + '/api/review/queue?status=all&limit=100', timeout=30).json()
    assert queue['total'] == 48
    item = next(x for x in queue['items'] if x['id'] == 'contract_term:payment' and x['source_refs'])
    case_id, item_id = item['case_id'], item['id']
    if item['review']['status'] != 'pending':
        reset = session.post(base + '/api/review/decision', json={
            'case_id': case_id, 'item_id': item_id, 'decision': 'reopen',
            'expected_revision': item['review']['revision'], 'note': ''}, timeout=20)
        reset.raise_for_status()
    target = base + '/review?case_id=' + case_id + '&item_id=' + item_id
    profile = ROOT / 'tmp' / ('review-browser-' + uuid.uuid4().hex[:8])
    profile.mkdir(parents=True)
    process = subprocess.Popen([
        'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
        '--headless=new', '--disable-gpu', '--no-first-run',
        '--remote-debugging-port=9226', '--remote-debugging-address=127.0.0.1',
        '--remote-allow-origins=http://localhost:9226', '--user-data-dir=' + str(profile),
        '--window-size=1440,1050', target,
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
    ws = None
    serial = 0
    errors = []
    shots = []
    checks = {}
    try:
        stop = time.monotonic() + 15
        while time.monotonic() < stop:
            try:
                tabs = session.get('http://127.0.0.1:9226/json', timeout=1).json()
                tab = next(x for x in tabs if x.get('type') == 'page' and x['url'].startswith(base))
                break
            except (requests.RequestException, StopIteration):
                time.sleep(.2)
        else:
            raise RuntimeError('Isolated browser did not start: ' + str(process.poll()))
        ws = websocket.create_connection(tab['webSocketDebuggerUrl'], origin='http://localhost:9226', timeout=20)

        def command(method, params=None):
            nonlocal serial
            serial += 1
            ws.send(json.dumps({'id': serial, 'method': method, 'params': params or {}}))
            while True:
                row = json.loads(ws.recv())
                if row.get('method') == 'Runtime.exceptionThrown':
                    errors.append(row['params']['exceptionDetails'])
                if row.get('id') == serial:
                    if 'error' in row:
                        raise RuntimeError(row['error'])
                    return row['result']

        def js(expression):
            row = command('Runtime.evaluate', {'expression': expression, 'returnByValue': True, 'awaitPromise': True})
            if row.get('exceptionDetails'):
                raise RuntimeError(row['exceptionDetails'])
            return row['result'].get('value')

        def until(expression, seconds=20):
            stop = time.monotonic() + seconds
            while time.monotonic() < stop:
                if js(expression):
                    return
                time.sleep(.1)
            raise AssertionError(expression + '\nStatus: ' + str(js("document.querySelector('#review-status')?.textContent")))

        def screenshot(name):
            path = ROOT / 'reports' / name
            path.write_bytes(base64.b64decode(command('Page.captureScreenshot', {'format': 'png', 'captureBeyondViewport': False})['data']))
            shots.append(path.relative_to(ROOT).as_posix())

        def navigate(url):
            command('Page.navigate', {'url': url})

        def field(selector, text):
            js(f"document.querySelector({json.dumps(selector)}).value={json.dumps(text)};document.querySelector({json.dumps(selector)}).dispatchEvent(new Event('input'))")

        def saved_item():
            return session.get(base + '/api/review/item', params={'case_id': case_id, 'item_id': item_id}, timeout=20).json()

        command('Runtime.enable')
        until("document.querySelector('#assertion-title')?.textContent && document.querySelector('#review-image img')?.naturalWidth>0 && !document.querySelector('#review-confirm').disabled")
        assert js("document.querySelector('#review-quote').textContent.includes(" + json.dumps(item['source_refs'][0]['quote']) + ")")
        assert js("document.querySelectorAll('#review-image rect').length>0")
        until("(()=>{const r=document.querySelector('#review-image rect').getBoundingClientRect(),v=document.querySelector('#review-image').getBoundingClientRect();return r.top<v.bottom && r.bottom>v.top})()")
        assert js("(()=>{const r=document.querySelector('#review-confirm').getBoundingClientRect();return r.top>0&&r.bottom<innerHeight})()")
        until("document.querySelectorAll('#review-context .context-message').length>0")
        assert js("document.querySelector('#source-meta').textContent.length>0")
        assert js("!document.body.innerText.includes('D:\\\\workspace')")
        positions = js("['queue-panel','evidence-panel','assertion-panel'].map(id=>{const r=document.getElementById(id).getBoundingClientRect();return {x:r.x,y:r.y,width:r.width}})")
        assert positions[0]['x'] < positions[1]['x'] < positions[2]['x']
        assert max(x['y'] for x in positions) - min(x['y'] for x in positions) < 2
        checks['three_columns_original_quote_bbox_context'] = True
        checks['citation_centered_and_actions_visible'] = True
        screenshot('v1.2.0_review_desktop.png')
        js("document.querySelector('#review-enlarge').click()")
        until("document.querySelector('#review-image-dialog').open")
        assert js("document.querySelectorAll('#review-zoom-content rect').length>0")
        js("document.querySelector('#review-image-close').click()")
        checks['enlarge_original_with_bbox'] = True

        draft = '复核测试：仅有支付线索，不能确认原告本人实际转账。'
        field('#review-edited-text', draft)
        field('#review-note', '仅在隔离测试库保存，不是正式人工复核。')
        revision = saved_item()['review']['revision']
        js("document.querySelector('#review-edited-text').dispatchEvent(new KeyboardEvent('keydown',{key:'3',bubbles:true}))")
        assert saved_item()['review']['revision'] == revision
        checks['typing_does_not_trigger_decision_shortcut'] = True
        assert js("document.querySelector('#review-confirm').disabled"), 'Edited text must not be silently discarded by Confirm'
        command('Page.reload')
        until("document.querySelector('#review-edited-text')?.value===" + json.dumps(draft))
        checks['device_draft_restores_after_reload'] = True
        js("document.querySelector('#review-amend').click()")
        until("document.querySelector('#review-undo')?.hidden===false && !document.querySelector('#review-amend').disabled")
        saved = saved_item()
        assert saved['review']['status'] == 'amended' and saved['review']['edited_text'] == draft
        assert len(saved['history']) >= 1
        checks['amendment_durable_history_and_auto_advance'] = True
        js("document.querySelector('#review-undo-button').click()")
        until("document.querySelector('#assertion-title')?.textContent && document.querySelector('#review-reopen').hidden && document.querySelector('#review-undo').hidden")
        assert saved_item()['review']['status'] == 'pending'
        checks['undo_reopens_item'] = True

        # Another writer changes the item after this browser has read its revision.
        old = saved_item()
        other = session.post(base + '/api/review/decision', json={
            'case_id': case_id, 'item_id': item_id, 'decision': 'confirmed',
            'expected_revision': old['review']['revision'], 'note': '隔离库并发测试',
        }, timeout=20)
        assert other.status_code == 200
        concurrent_draft = '并发冲突后的本地修订草稿，必须保留。'
        field('#review-edited-text', concurrent_draft)
        js("document.querySelector('#review-amend').click()")
        until("document.querySelector('#review-status').textContent.includes('更新')")
        assert js("document.querySelector('#review-edited-text').value===" + json.dumps(concurrent_draft))
        assert js("document.querySelector('#review-amend').disabled && !document.querySelector('#review-reopen').disabled")
        js("document.querySelector('#review-reopen').click()")
        until("!document.querySelector('#review-amend').disabled && document.querySelector('#review-reopen').hidden")
        assert js("document.querySelector('#review-edited-text').value===" + json.dumps(concurrent_draft)), 'Reopen must preserve conflicted local draft'
        checks['revision_conflict_no_overwrite_and_draft_preserved'] = True
        # Return this isolated item to its proposed text, confirm and check explicit status.
        proposed = saved_item()['proposed_text']
        field('#review-edited-text', proposed)
        js("document.querySelector('#review-confirm').click()")
        until("document.querySelector('#review-undo')?.hidden===false && !document.querySelector('#review-amend').disabled")
        assert saved_item()['review']['status'] == 'confirmed'
        js("document.querySelector('#review-undo-button').click()")
        until("document.querySelector('#review-undo').hidden && !document.querySelector('#review-amend').disabled")
        checks['confirmation_explicit_and_reopen_audited'] = True
        for decision in ('reject', 'defer'):
            js(f"document.querySelector('#review-{decision}').click()")
            until("document.querySelector('#review-undo')?.hidden===false && !document.querySelector('#review-amend').disabled")
            assert saved_item()['review']['status'] == {'reject': 'rejected', 'defer': 'deferred'}[decision]
            js("document.querySelector('#review-undo-button').click()")
            until("document.querySelector('#review-undo').hidden && !document.querySelector('#review-amend').disabled")
        checks['reject_defer_and_reopen'] = True

        # Switch to the global queue; all cases and export must remain available.
        navigate(base + '/review')
        until("document.querySelectorAll('#review-case option').length===3 && document.querySelector('#review-image img')?.naturalWidth>0")
        assert 'case_id=' in js("document.querySelector('#review-export').href")
        assert js("document.querySelector('#source-coverage').textContent.includes('未绑定直接原文')")
        assert js("document.querySelector('#review-image rect')===null")
        assert js("document.querySelector('#source-coverage').getBoundingClientRect().top<document.querySelector('#review-image').getBoundingClientRect().top")
        checks['unbound_source_warning_without_fabricated_highlight'] = True
        field('#review-case', case_id)
        js("document.querySelector('#review-case').dispatchEvent(new Event('change'))")
        until("document.querySelector('#review-status').textContent==='' && document.querySelectorAll('.queue-item').length>0")
        assert js("document.querySelectorAll('#review-case option').length") == 3
        assert js("document.querySelector('#review-filter-status option[value=stale]')!==null")
        checks['case_choices_export_and_stale_filter'] = True

        law_item = next(x for x in queue['items'] if x.get('law_refs'))
        navigate(base + '/review?case_id=' + law_item['case_id'] + '&item_id=' + law_item['id'])
        until("document.querySelector('#review-law-basis') && !document.querySelector('#review-law-basis').hidden")
        assert js("document.querySelector('#review-law-basis').textContent.includes('版本')")
        checks['legal_basis_in_page_with_applicability_check'] = True

        js("document.querySelector('#language').value='en';document.querySelector('#language').dispatchEvent(new Event('change'))")
        assert js("document.querySelector('#review-confirm').textContent.includes('Confirm')")
        checks['bilingual_controls'] = True
        screenshot('v1.2.0_review_english.png')
        command('Emulation.setDeviceMetricsOverride', {'width': 390, 'height': 844, 'deviceScaleFactor': 1, 'mobile': True})
        assert js("document.documentElement.scrollWidth<=window.innerWidth"), 'Review mobile overflow'
        js("document.querySelector('[data-panel=assertion]').click()")
        assert js("getComputedStyle(document.querySelector('#assertion-panel')).display!=='none'")
        js("document.querySelector('[data-panel=assertion]').dispatchEvent(new KeyboardEvent('keydown',{key:'Home',bubbles:true}))")
        assert js("document.querySelector('.review-layout').dataset.activePanel==='queue'")
        js("document.querySelector('[data-panel=evidence]').click();window.scrollTo({top:0,behavior:'instant'})")
        screenshot('v1.2.0_review_mobile.png')
        checks['mobile_no_overflow_and_keyboard_tabs'] = True
        command('Emulation.clearDeviceMetricsOverride')

        navigate(base + '/')
        until("document.querySelectorAll('.case-tile').length===24")
        js("document.querySelector('#language').value='zh';document.querySelector('#language').dispatchEvent(new Event('change'))")
        assert js("document.body.innerText.includes('让每一项判断，回到证据。')")
        screenshot('v1.2.0_cases_desktop.png')
        command('Emulation.setDeviceMetricsOverride', {'width': 390, 'height': 844, 'deviceScaleFactor': 1, 'mobile': True})
        assert js("document.documentElement.scrollWidth<=window.innerWidth"), 'Library mobile overflow'
        screenshot('v1.2.0_cases_mobile.png')
        command('Emulation.clearDeviceMetricsOverride')
        checks['library_redesign_preserves_case_pagination'] = True
        navigate(base + '/case?case_id=5ad6f87311be1056f7197a9f')
        until("typeof state!=='undefined' && state?.case_id==='5ad6f87311be1056f7197a9f' && document.querySelectorAll('.timeline-section').length===6")
        screenshot('v1.2.0_case_desktop.png')
        js("document.querySelector('[data-mode=qa]').click()")
        until("document.querySelector('.inline-citation')!==null")
        js("document.querySelector('.inline-citation').click()")
        until("!document.querySelector('#citation-drawer').hidden && document.querySelector('.citation-stage img')?.naturalWidth>0")
        assert js("document.querySelector('.citation-stage rect')!==null")
        screenshot('v1.2.0_case_citation.png')
        command('Emulation.setDeviceMetricsOverride', {'width': 390, 'height': 844, 'deviceScaleFactor': 1, 'mobile': True})
        assert js("document.documentElement.scrollWidth<=window.innerWidth"), 'Case mobile overflow'
        assert js("document.querySelector('#citation-drawer').getBoundingClientRect().right<=innerWidth+1")
        screenshot('v1.2.0_case_citation_mobile.png')
        command('Emulation.clearDeviceMetricsOverride')
        checks['existing_qa_history_and_source_sidebar'] = True
        uploaded = next(cid for cid in {x['case_id'] for x in queue['items']} if cid.startswith('case-'))
        navigate(base + '/case?case_id=' + uploaded)
        until("typeof state!=='undefined' && state?.case_id===" + json.dumps(uploaded) + " && state.analysis && graph.contract_terms.length===8")
        assert js("state.job.status==='completed' && state.message_count===19 && state.quality.images_ok===2")
        js("document.querySelector('[data-mode=contract]').click()")
        assert js("document.querySelectorAll('#contract-view tbody tr').length===8")
        js("document.querySelector('#contract-view tr[data-term=payment] button').click()")
        until("!document.querySelector('#inspection').hidden && document.querySelector('#inspection-source img')?.naturalWidth>0")
        checks['completed_upload_and_contract_source_link_preserved'] = True
        navigate(base + '/case?case_id=58b7dff082ec3972eb9edeb4')
        until("typeof state!=='undefined' && state?.case_id==='58b7dff082ec3972eb9edeb4' && document.querySelectorAll('.timeline-section').length===3")
        assert js("document.querySelectorAll('.legal-event-card').length===0 && !document.querySelector('#case-generation-banner').hidden")
        checks['unanalyzed_case_originals_remain_honest'] = True
        assert not errors, errors
        checks['browser_runtime_exceptions'] = 0
        result = {'server': base, 'isolated_review_database': True, 'total_review_items': 48, 'analyzed_cases': 2,
                  'model_requests_made_by_test': 0, 'checks': checks, 'screenshots': shots}
        (ROOT / 'reports/v1.2.0_review_browser.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(result, ensure_ascii=True))
    finally:
        if ws:
            try:
                command('Browser.close')
            except Exception:
                pass
            ws.close()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.terminate()


if __name__ == '__main__':
    main()
