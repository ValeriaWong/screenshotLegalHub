"""Render local HTML chat interfaces with isolated headless Chromium via CDP.

No original screenshot editing, network pages, signed-in browser, or external API.
"""
from pathlib import Path
from datetime import datetime
import base64, hashlib, html, json, os, shutil, subprocess, sys, time, urllib.request
import websocket

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'datasets/v2.0.0/round_002'
CHROME=Path(os.environ.get('LOCALAPPDATA','C:/Users/godli/AppData/Local'))/'ms-playwright/chromium-1200/chrome-win64/chrome.exe'
WIDTH,HEIGHT,SCALE=430,932,2
STYLE_VERSION='wechat-github-reference-20261106'
WECHAT_STYLE=Path(__file__).resolve().parent/'templates/wechat.css'

CSS=r'''
*{box-sizing:border-box}html,body{margin:0;width:430px;height:932px;overflow:hidden}body{font-family:"Microsoft YaHei","Segoe UI",sans-serif;color:#171717}
.phone{width:430px;height:932px;display:flex;flex-direction:column;background:#ededed}.status{height:30px;flex-shrink:0;display:flex;align-items:center;justify-content:space-between;padding:0 23px;font-family:Arial;font-size:14px;font-weight:600}.status .icons{display:flex;align-items:center;gap:6px}.battery{width:23px;height:11px;border:1px solid currentColor;border-radius:3px;padding:2px;position:relative}.battery:before{content:"";display:block;height:100%;width:82%;background:currentColor}.battery:after{content:"";position:absolute;right:-3px;top:3px;width:2px;height:4px;background:currentColor}
.header{height:58px;flex-shrink:0;display:flex;align-items:center;gap:12px;padding:0 15px;border-bottom:1px solid #ddd}.chevron{width:10px;height:10px;border-left:2px solid currentColor;border-bottom:2px solid currentColor;transform:rotate(45deg);margin:0 6px}.title{flex:1;font-size:18px;font-weight:500}.dots{font-size:24px;letter-spacing:2px;line-height:20px}.head-ava{display:none}.content{flex:1;overflow:hidden;padding:12px 13px 8px}.row{margin-bottom:12px}.stamp{text-align:center;font-size:12px;color:#939393;line-height:18px;margin:10px 0 13px}.line{display:flex;gap:9px;align-items:flex-start}.avatar{width:38px;height:38px;flex:0 0 38px;border-radius:5px;display:flex;justify-content:center;align-items:center;font-size:18px;color:#fff;background:var(--av)}.row.out .line{flex-direction:row-reverse}.bubble{max-width:307px;min-width:28px;background:white;border-radius:5px;padding:9px 12px;line-height:25px;font-size:17px;position:relative;overflow-wrap:anywhere;white-space:pre-wrap}.bubble:before{content:"";position:absolute;top:14px;left:-5px;border-right:6px solid white;border-top:5px solid transparent;border-bottom:5px solid transparent}.out .bubble{background:#95ec69}.out .bubble:before{left:auto;right:-5px;border-right:0;border-left:6px solid #95ec69}.sender{font-size:12px;color:#597687;margin-bottom:3px}.bubble .time{display:none}.file{display:flex;gap:10px;align-items:center;min-width:247px;white-space:normal}.doc{width:38px;height:45px;background:#dc5a53;color:white;flex-shrink:0;display:flex;align-items:center;justify-content:center;font-family:Arial;font-size:11px;border-radius:3px}.filename{font-size:15px;line-height:21px}.filetype{font-size:11px;color:#999;margin-top:3px}.bubble.file-bubble{background:white}.out .file-bubble:before{border-left-color:white}.excerpt{background:#fff;color:#333;min-width:257px;white-space:normal;border:1px solid #cdd1d4;padding:12px 9px;font-family:"Microsoft YaHei",sans-serif}.excerpt h3{font-size:13px;line-height:20px;margin:0 0 11px;color:#333}.excerpt table{border-collapse:collapse;width:100%;font-size:12px;line-height:19px}.excerpt td{padding:5px 4px;border:1px solid #bbc2c5}.excerpt td:first-child{color:#666;width:38%}.excerpt footer{font-size:10px;text-align:right;margin-top:9px;color:#777}.bubble.picture-bubble{padding:3px;background:white}.out .picture-bubble:before{border-left-color:white}.picture-caption{padding:5px 7px;font-size:14px;line-height:20px}
.input{height:65px;flex-shrink:0;background:#f6f6f6;border-top:1px solid #d9d9d9;display:flex;gap:13px;padding:11px 13px 19px;align-items:center}.input-box{height:35px;background:white;border-radius:5px;flex:1}.round-icon{width:25px;height:25px;border:1.6px solid #444;border-radius:50%;position:relative;flex-shrink:0}.plus:before,.plus:after{content:"";position:absolute;background:#444;left:5px;right:5px;top:10px;height:1.5px}.plus:after{transform:rotate(90deg)}.smile:before{content:"••";position:absolute;font-size:10px;letter-spacing:4px;top:0;left:5px}.smile:after{content:"";position:absolute;width:10px;height:5px;border-bottom:1.3px solid #444;border-radius:50%;left:6px;top:11px}.voice{border:0;border-radius:0}.voice:before{content:"";position:absolute;width:13px;height:20px;left:1px;top:1px;border-right:2px solid #444;border-radius:50%}.voice:after{content:"";position:absolute;width:20px;height:25px;left:0;top:-1px;border-right:2px solid #444;border-radius:50%}
.wa{background:#efeae2}.wa .status,.wa .header{background:#075e54;color:white}.wa .header{border:0;height:61px;padding-left:13px}.wa .head-ava{display:flex;width:37px;height:37px;background:#8fae9b;border-radius:50%;align-items:center;justify-content:center;font-size:15px;color:white}.wa .title{font-size:17px}.wa .subtitle{font-size:11px;opacity:.8;margin-top:3px}.wa .content{background-image:url('../../assets/whatsapp-bg.png');background-size:430px;background-blend-mode:multiply;padding:12px 12px 8px}.wa .avatar{display:none}.wa .bubble{max-width:342px;font-size:16px;line-height:23px;border-radius:7px;padding:7px 10px 6px;box-shadow:0 1px 1px #0002;word-break:normal;overflow-wrap:break-word}.wa .out .line{justify-content:flex-start}.wa .out .bubble{background:#d9fdd3}.wa .out .bubble:before{border-left-color:#d9fdd3}.wa .bubble:before{top:0;left:-6px;border-top:0;border-bottom:9px solid transparent;border-right:8px solid white}.wa .out .bubble:before{left:auto;right:-6px;border-left:8px solid #d9fdd3}.wa .bubble .time{display:block;text-align:right;font-size:10px;line-height:12px;color:#6e7f76;margin:4px 0 -1px 25px}.wa .stamp{margin:8px auto 12px;background:#ffffffe3;color:#626a6d;border-radius:6px;width:max-content;padding:4px 9px;font-size:11px;box-shadow:0 1px 1px #0001}.wa .input{border:0;background:#efeae2;height:62px;padding:6px 8px 15px;gap:10px}.wa .input-box{border-radius:24px;padding:8px 13px;font-size:15px;color:#89948f;height:40px}.wa .mic{background:#008069;color:white;width:40px;height:40px;border-radius:50%;display:flex;align-items:center;justify-content:center}.wa .sender{font-weight:600;font-size:12px;color:var(--av);margin-bottom:3px}.wa .row{margin-bottom:8px}
.row{display:flow-root}.wa{font-family:"Segoe UI",Arial,sans-serif}.wa .out .bubble:before{border-right:0}.footnote{position:absolute;bottom:2px;left:0;width:430px;text-align:center;font-size:8px;letter-spacing:.7px;color:#7f8981;pointer-events:none}.phone:not(.wa) .footnote{color:#999}
.title{min-width:0}.title-text,.subtitle{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.bubble-column{min-width:0;max-width:307px}.phone:not(.wa) .bubble-column>.sender{color:#8c8c8c;margin:0 0 4px 2px}.wa .bubble-column{max-width:342px}
.bubble.transfer-bubble{padding:0;overflow:hidden;background:#f5a23d;color:white;min-width:245px}.out .transfer-bubble:before{border-left-color:#f5a23d}.transfer-top{padding:15px 14px;display:flex;gap:12px;align-items:center}.transfer-icon{border:1.5px solid white;border-radius:50%;width:35px;height:35px;display:flex;align-items:center;justify-content:center;font-size:23px}.transfer-amount{font-size:21px}.transfer-label{font-size:12px;line-height:18px}.transfer-footer{background:white;color:#999;padding:3px 12px;font-size:10px;line-height:18px}
.voice-transcript-label{font-size:11px;color:#737b71;margin-bottom:5px;line-height:18px}.voice-transcript-label:before{content:"◖ ";font-size:15px}
'''


CSS+='\n'+WECHAT_STYLE.read_text(encoding='utf-8')


def esc(s):return html.escape(str(s))


def avatar_html(person,people,platform):
    """Local decorative avatars; no claim to reconstruct a participant's photo."""
    if platform!='wechat':
        return esc(person['name'][0] if platform!='whatsapp' else ''.join(p[0] for p in person['name'].split()))
    index=list(people).index(person['id']) if person.get('id') in people else 0
    palettes=[('#dde8e2','#8caaa0','#476d65','#fbecba'),
              ('#e6e1dc','#b3a594','#827369','#fff0c9'),
              ('#dee8ef','#91abbc','#4b6c85','#f8ead4'),
              ('#ebe3d8','#b1b99a','#708268','#fff2cb')]
    sky,hill,foreground,sun=palettes[index%len(palettes)]
    if index%2:
        art=f'<path d="M0 49Q22 37 44 51T88 48V88H0Z" fill="{hill}"/><path d="M0 68Q30 52 60 65T88 63V88H0Z" fill="{foreground}"/><path d="M64 63V25M64 45Q45 48 47 29Q64 27 64 45M64 36Q81 36 79 18Q63 20 64 36" fill="{foreground}" stroke="{foreground}" stroke-width="2"/>'
    else:
        art=f'<path d="M0 64 27 29 58 65 74 42 88 61V88H0Z" fill="{hill}"/><path d="m17 42 10-13 12 14-12-5Z" fill="#f5f4ec"/><path d="M0 74Q26 58 49 73T88 70V88H0Z" fill="{foreground}"/>'
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 88 88" aria-hidden="true"><rect width="88" height="88" fill="{sky}"/><circle cx="22" cy="21" r="9" fill="{sun}"/>{art}</svg>'


def toolbar_icon(kind):
    shapes={
        'voice':'<circle cx="16" cy="16" r="13.5"/><path d="M12 13v6m4-9a10 10 0 0 1 0 12m4-15a15 15 0 0 1 0 18"/>',
        'smile':'<circle cx="16" cy="16" r="13.5"/><circle cx="11" cy="12" r="1" fill="currentColor" stroke="none"/><circle cx="21" cy="12" r="1" fill="currentColor" stroke="none"/><path d="M9 19c2 7 12 7 14 0"/>',
        'plus':'<circle cx="16" cy="16" r="13.5"/><path d="M16 8v16M8 16h16"/>',
    }
    return f'<span class="toolbar-icon" aria-hidden="true"><svg viewBox="0 0 32 32" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round">{shapes[kind]}</svg></span>'


def phone_html(conv,people,platform,content=''):
    """Shared chrome for current V2 rendering and explicitly selected V3 previews."""
    names=[people[ident]['name'] for ident in conv['participant_ids']]
    subtitle='<div class="subtitle">'+esc(', '.join(names))+'</div>' if platform=='whatsapp' and conv.get('is_group') else ''
    avatar=f'<div class="head-ava">{esc(conv["title"][:1])}</div>' if platform!='wechat' else ''
    dots='<i></i><i></i><i></i>' if platform=='wechat' else '···'
    header=f'<div class="chevron"></div>{avatar}<div class="title"><div class="title-text">{esc(conv["title"])}</div>{subtitle}</div><div class="dots">{dots}</div>'
    icons='<svg width="18" height="12" viewBox="0 0 18 12" fill="currentColor" aria-hidden="true"><rect x="0" y="8" width="3" height="4" rx=".6"/><rect x="5" y="5" width="3" height="7" rx=".6"/><rect x="10" y="2" width="3" height="10" rx=".6"/><rect x="15" width="3" height="12" rx=".6"/></svg><svg width="17" height="12" viewBox="0 0 17 12" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M1 3Q8.5 -2 16 3M3.5 6Q8.5 2.5 13.5 6M6 9Q8.5 7 11 9"/><circle cx="8.5" cy="11" r=".7" fill="currentColor" stroke="none"/></svg><span class="battery"></span>'
    if platform=='wechat':
        controls=toolbar_icon('voice')+'<div class="input-box"></div>'+toolbar_icon('smile')+toolbar_icon('plus')
    elif platform=='whatsapp':
        controls='<div class="input-box">☺ &nbsp; Message &nbsp;&nbsp;&nbsp;⌕</div><div class="mic">♩</div>'
    else:
        controls='<div class="round-icon voice"></div><div class="input-box"></div><div class="round-icon smile"></div><div class="round-icon plus"></div>'
    skin='wa' if platform=='whatsapp' else 'wechat' if platform=='wechat' else 'neutral'
    home='<div class="home-indicator"></div>' if platform=='wechat' else ''
    note='合成研究样本' if platform=='wechat' else 'SYNTHETIC · RESEARCH SAMPLE'
    return f'<div class="phone {skin}"><div class="status"><span>9:41</span><div class="icons">{icons}</div></div><div class="header">{header}</div><div class="content" id="messages">{content}</div><div class="input">{controls}</div>{home}<div class="footnote">{note}</div></div>'


def message_html(m,conversation,people,previous,platform):
    is_out=m['sender_id']==conversation['viewer_id']
    current=datetime.fromisoformat(m['timestamp']) if m.get('timestamp') else None
    prior=datetime.fromisoformat(previous['timestamp']) if previous and previous.get('timestamp') else None
    stamp=''
    if current and (not prior or current.date()!=prior.date() or (platform!='whatsapp' and (current-prior).total_seconds()>=600)):
        label=current.strftime('%-d %B %Y') if False else current.strftime('%d %b %Y').lstrip('0')
        if platform!='whatsapp':
            label=f'{current.year}年{current.month}月{current.day}日'
            if m.get('minute_basis') not in {'not_visible','source_day_only'}:
                label+=f' {current:%H:%M}'
        stamp=f'<div class="stamp">{esc(label)}</div>'
    elif not current and m.get('date_basis')=='source_month' and m.get('time_label'):
        if not previous or previous.get('time_label')!=m['time_label']:
            stamp=f'<div class="stamp">{esc(m["time_label"])}</div>'
    person=people[m['sender_id']];colors={'li':'#668c85','chen':'#aa9675','liu':'#7c91a4','oo':'#876eab','sr':'#308f88','sh':'#b37759','sk':'#578cab'}
    palette=['#668c85','#aa9675','#7c91a4','#876eab','#308f88','#b37759','#578cab']
    av=colors.get(m['sender_id'],palette[int(hashlib.sha256(m['sender_id'].encode()).hexdigest()[:4],16)%len(palette)])
    avatar=avatar_html(person,people,platform)
    group_name=f'<div class="sender">{esc(person["name"])}</div>' if conversation.get('is_group') and not is_out else ''
    klass='';body=esc(m['text'])
    if m.get('original_medium')=='voice_transcription_in_judgment':
        body='<div class="voice-transcript-label">语音转文字</div>'+body
    if m['kind']=='transfer':
        klass=' transfer-bubble'
        amount=float(m['transfer']['amount'])
        receipt=m['transfer'].get('receipt_status','not_reconstructed')
        label={'expired':'已过期','received':'已被接收'}.get(receipt,'转账')
        if platform=='wechat':
            if receipt in {'received','expired'}:klass+=' transfer-'+receipt
            shape='<circle cx="20" cy="20" r="16"/><path d="m12 20 6 6 11-12"/>' if receipt=='received' else '<path d="M7 14h25l-7-7M33 26H8l7 7"/>'
            icon=f'<svg viewBox="0 0 40 40" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{shape}</svg>'
        else:icon='↔'
        body=f'<div class="transfer-top"><div class="transfer-icon">{icon}</div><div class="transfer-details"><div class="transfer-amount">¥{amount:,.2f}</div><div class="transfer-label">{label}</div></div></div><div class="transfer-footer">微信转账</div>'
    elif m['kind']=='file':
        kind=m.get('file_type','文档');description=kind if kind in ['文档','视频','音频','图片'] else kind+' 文档'
        klass=' file-bubble';body=f'<div class="file"><div class="doc">{esc(kind)}</div><div><div class="filename">{body}</div><div class="filetype">{esc(description)}</div></div></div>'
    elif m['kind']=='attachment_excerpt':
        klass=' picture-bubble';a=m['attachment'];rows=''.join(f'<tr><td>{esc(k)}</td><td>{esc(v)}</td></tr>' for k,v in a['rows'])
        body=f'<div class="excerpt"><h3>{esc(a["title"])}</h3><table>{rows}</table><footer>{esc(a.get("footer", ""))}</footer></div>'
        if m['text']:body+=f'<div class="picture-caption">{esc(m["text"])}</div>'
    shown_time=current.strftime('%H:%M') if current else ''
    inside=group_name if platform=='whatsapp' else ''
    outside=group_name if platform!='whatsapp' else ''
    return f'<div class="row {"out" if is_out else "in"}" data-id="{esc(m["id"])}" style="--av:{av}">{stamp}<div class="line"><div class="avatar">{avatar}</div><div class="bubble-column">{outside}<div class="bubble{klass}">{inside}{body}<span class="time">{shown_time}</span></div></div></div></div>'


class Browser:
    def __init__(self,profile_name='chrome-round2'):
        self.profile_name=profile_name

    def __enter__(self):
        profile=ROOT/'.runtime'/self.profile_name;profile.mkdir(parents=True,exist_ok=True)
        portfile=profile/'DevToolsActivePort'
        if portfile.exists():portfile.unlink()
        self.log=(profile/'render.log').open('w',encoding='utf-8')
        self.process=subprocess.Popen([str(CHROME),'--headless','--disable-gpu','--in-process-gpu','--no-sandbox','--disable-gpu-sandbox','--no-first-run','--no-default-browser-check',
            '--remote-debugging-port=0','--remote-allow-origins=http://localhost',f'--user-data-dir={profile}',
            '--disable-background-networking','--disable-component-update','about:blank'],stdout=subprocess.DEVNULL,
            stderr=self.log,creationflags=subprocess.CREATE_NO_WINDOW if sys.platform=='win32' else 0)
        deadline=time.monotonic()+20
        while not portfile.exists():
            if time.monotonic()>deadline:raise RuntimeError('Local Chromium did not start')
            time.sleep(.15)
        port=int(portfile.read_text().splitlines()[0])
        targets=json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/json/list'))
        self.ws=websocket.create_connection(next(t['webSocketDebuggerUrl'] for t in targets if t['type']=='page'),origin='http://localhost',timeout=20, http_no_proxy=['127.0.0.1','localhost'])
        self.counter=0
        self.call('Page.enable')
        self.call('Emulation.setDeviceMetricsOverride',{'width':WIDTH,'height':HEIGHT,'deviceScaleFactor':SCALE,'mobile':False})
        return self

    def call(self,method,params=None):
        self.counter+=1;ident=self.counter
        self.ws.send(json.dumps({'id':ident,'method':method,'params':params or {}}))
        while True:
            response=json.loads(self.ws.recv())
            if response.get('id')==ident:
                if 'error' in response:raise RuntimeError(response['error'])
                return response.get('result',{})

    def evaluate(self,expression):
        result=self.call('Runtime.evaluate',{'expression':expression,'returnByValue':True,'awaitPromise':True})
        if result.get('exceptionDetails'):raise RuntimeError(result['exceptionDetails'])
        return result['result'].get('value')

    def load(self,path):
        self.call('Page.navigate',{'url':path.resolve().as_uri()})
        for _ in range(100):
            if self.evaluate('document.readyState')=='complete':break
            time.sleep(.05)
        self.evaluate('document.fonts.ready.then(()=>true)')

    def capture(self,path):
        self.evaluate('window.scrollTo(0,0);true')
        self.evaluate('new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(()=>r(true))))')
        data=self.call('Page.captureScreenshot',{'format':'png','captureBeyondViewport':False,'fromSurface':True})['data']
        path.write_bytes(base64.b64decode(data))

    def __exit__(self,*args):
        try:self.call('Browser.close')
        except Exception:pass
        self.ws.close();self.log.close()
        try:self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:self.process.terminate()


def render_case(browser,directory):
    case=json.loads((directory/'case.json').read_text(encoding='utf-8'));people={p['id']:p for p in case['participants']}
    platform=case['platform'].lower();platform='whatsapp' if case['language']=='en' else 'wechat'
    if case.get('source_medium') and platform=='wechat':platform='neutral'
    images=[];screens=directory/'screenshots';screens.mkdir(exist_ok=True)
    for conv in case['conversations']:
        messages=[m for m in case['messages'] if m['conversation_id']==conv['id']]
        rows=[message_html(m,conv,people,messages[i-1] if i else None,platform) for i,m in enumerate(messages)]
        phone=phone_html(conv,people,platform)
        script='window.rows='+json.dumps(rows,ensure_ascii=False).replace('<','\\u003c')+';window.show=(ids)=>{document.getElementById("messages").innerHTML=ids.map(i=>rows[i]).join("")};show(rows.map((_,i)=>i));'
        template='<!doctype html><html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>'+CSS+'</style><body>'+phone+'<script>'+script+'</script></body></html>'
        path=directory/f'{conv["id"]}.html';path.write_text(template,encoding='utf-8');browser.load(path)
        metrics=browser.evaluate('({limit:document.querySelector(".content").clientHeight-55, heights:Array.from(document.querySelectorAll(".row"),x=>x.getBoundingClientRect().height+parseFloat(getComputedStyle(x).marginBottom))})')
        pages=[];start=0;count=len(rows)
        unknown_boundaries={i for i in range(1,count) if not messages[i].get('timestamp') and messages[i-1].get('timestamp')}
        while start<count:
            if metrics['heights'][start]>metrics['limit']:
                pages.append({'indices':[start],'fragment':True});start+=1;continue
            stop=start;used=0
            while stop<count and used+metrics['heights'][stop]<=metrics['limit']:
                if stop>start and stop in unknown_boundaries:break
                used+=metrics['heights'][stop];stop+=1
            if stop==start:raise RuntimeError(f'Pagination made no progress {case["id"]}/{messages[start]["id"]}')
            pages.append({'indices':list(range(start,stop)),'fragment':False})
            if stop==count:break
            # One repeated message at a cut, if at least two fit; not a second send.
            start=stop if stop in unknown_boundaries else (stop-1 if stop-start>1 else stop)
        n=0
        for page in pages:
            indices=page['indices']
            browser.evaluate('show('+json.dumps(indices)+')')
            browser.evaluate('document.querySelector(".content").style.paddingTop="12px"')
            if not browser.evaluate('Boolean(document.querySelector(".row:first-child .stamp"))') and messages[indices[0]].get('timestamp'):
                first=messages[indices[0]];d=datetime.fromisoformat(first['timestamp'])
                stamp=d.strftime('%d %b %Y').lstrip('0') if platform=='whatsapp' else f'{d.year}年{d.month}月{d.day}日'
                if platform!='whatsapp' and first.get('minute_basis') not in {'not_visible','source_day_only'}:
                    stamp+=f' {d:%H:%M}'
                browser.evaluate('document.querySelector(".row").insertAdjacentHTML("afterbegin",'+json.dumps(f'<div class="stamp">{esc(stamp)}</div>')+')')
            elif not browser.evaluate('Boolean(document.querySelector(".row:first-child .stamp"))') and messages[indices[0]].get('date_basis')=='source_month' and messages[indices[0]].get('time_label'):
                stamp=messages[indices[0]]['time_label']
                browser.evaluate('document.querySelector(".row").insertAdjacentHTML("afterbegin",'+json.dumps(f'<div class="stamp">{esc(stamp)}</div>')+')')
            segments=[None]
            if page['fragment']:
                browser.evaluate('document.querySelector(".content").style.paddingTop="0px"')
                dimensions=browser.evaluate('({height:document.querySelector(".row").getBoundingClientRect().height,viewport:document.querySelector(".content").clientHeight-4})')
                # Overlap keeps line baselines visible on one of the adjacent crops.
                total=dimensions['height'];visible=dimensions['viewport'];offset=0;segments=[]
                while True:
                    segments.append({'message_id':messages[indices[0]]['id'],'offset_css':offset,
                                     'visible_height_css':min(visible,total-offset),'full_height_css':total,
                                     'same_message_scroll_crop':True})
                    if offset+visible>=total:break
                    offset=min(offset+visible-80,total-visible)
            for segment in segments:
                n+=1
                if segment:
                    browser.evaluate('document.querySelector(".row").style.transform="translateY(-'+str(segment['offset_css'])+'px)"')
                    # Clip to the chat viewport, without modifying the message text or ID.
                    boxes=browser.evaluate('Array.from(document.querySelectorAll(".row"),x=>{let b=x.getBoundingClientRect(),c=document.querySelector(".content").getBoundingClientRect();let top=Math.max(b.top,c.top),bottom=Math.min(b.bottom,c.bottom-4);return {message_id:x.dataset.id,bbox_css:[b.x,top,b.width,Math.max(0,bottom-top)],same_message_scroll_crop:true}})')
                else:
                    boxes=browser.evaluate('Array.from(document.querySelectorAll(".row"),x=>{let b=x.getBoundingClientRect();return {message_id:x.dataset.id,bbox_css:[b.x,b.y,b.width,b.height]}})')
                    bottom=browser.evaluate('document.querySelector(".content").getBoundingClientRect().bottom')
                    if any(b['bbox_css'][1]+b['bbox_css'][3]>bottom-3 for b in boxes):
                        raise RuntimeError(f'Clipped page {case["id"]}/{conv["id"]}/{n}')
                file=f'{conv["id"]}_{n:02d}.png';browser.capture(screens/file)
                for b in boxes:b['bbox_pixels']=[round(v*SCALE) for v in b['bbox_css']]
                images.append({'page':len(images)+1,'conversation_id':conv['id'],'path':'screenshots/'+file,
                               'message_ids':[messages[i]['id'] for i in indices],'boxes':boxes,'width':WIDTH*SCALE,'height':HEIGHT*SCALE,
                               **({'scroll_fragment':segment} if segment else {})})
    (directory/'render.json').write_text(json.dumps({'images':images,'css_viewport':[WIDTH,HEIGHT],'scale':SCALE,'style_version':STYLE_VERSION if platform=='wechat' else 'legacy-'+platform,'css_sha256':hashlib.sha256(CSS.encode()).hexdigest(),'overlap_policy':'one repeated message when it fits; oversized messages use overlapping scroll crops with the same ID'},ensure_ascii=False,indent=2),encoding='utf-8')
    return {'case_id':case['id'],'images':len(images)}


def main():
    assets=OUT/'assets';assets.mkdir(exist_ok=True)
    upstream=Path('D:/workspace/whatsapp-collection/whatsapp-simulator')
    for src,dst in [(upstream/'public/whatsapp-bg.png',assets/'whatsapp-bg.png'),(upstream/'LICENSE',assets/'whatsapp-simulator.LICENSE')]:shutil.copyfile(src,dst)
    (assets/'PROVENANCE.md').write_text('# 渲染资源来源\n\nWhatsApp 背景来自本地 whatsapp-collection/whatsapp-simulator/public/whatsapp-bg.png；该项目 MIT 许可随附。界面其余 HTML/CSS 本轮独立实现。没有使用私有头像或原始聊天截图。\n\n所有截图为合成研究样本；附件图片按判决记载重建，并非取得原件。\n',encoding='utf-8')
    results=[]
    with Browser() as browser:
        for directory in sorted(OUT.glob('*/*')):
            if (directory/'case.json').exists():results.append(render_case(browser,directory))
    print(json.dumps(results,ensure_ascii=False))


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');main()
