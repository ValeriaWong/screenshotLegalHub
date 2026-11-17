"""A long single message must stay intact while screenshots cover its full viewport range."""
import sys,json
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.render_v2_round2 import Browser,render_case

if __name__=='__main__':
    directory=ROOT/'.runtime/v2_scroll_fixture';directory.mkdir(parents=True,exist_ok=True)
    text='连续视口测试：原消息不拆分。'+''.join(f'第{i}句原文，时间和金额都保持同一条消息。' for i in range(160))
    c={'id':'scroll_fixture','language':'zh','platform':'WeChat',
       'participants':[{'id':'a','name':'甲'},{'id':'b','name':'乙'}],
       'conversations':[{'id':'c1','title':'乙','viewer_id':'a','participant_ids':['a','b'],'is_group':False}],
       'messages':[{'id':'long1','conversation_id':'c1','sender_id':'b','timestamp':'2024-01-02 09:10',
                    'kind':'text','text':text},
                   {'id':'reply1','conversation_id':'c1','sender_id':'a','timestamp':'2024-01-02 09:12','kind':'text','text':'看到了'}]}
    (directory/'case.json').write_text(json.dumps(c,ensure_ascii=False),encoding='utf-8')
    with Browser('chrome-scroll-fixture') as browser:render_case(browser,directory)
    r=json.loads((directory/'render.json').read_text(encoding='utf-8'));spans=[];chrome=None
    for shot in r['images']:
        with Image.open(directory/shot['path']) as im:
            assert im.size==(860,1864)
            current=(im.crop((0,0,860,176)).tobytes(),im.crop((0,1738,860,1864)).tobytes())
            if chrome:assert current==chrome
            chrome=current
        if shot.get('scroll_fragment'):
            f=shot['scroll_fragment'];assert f['message_id']=='long1'
            spans.append((f['offset_css'],f['offset_css']+f['visible_height_css'],f['full_height_css']))
    assert len(spans)>1 and spans[0][0]==0
    assert all(spans[i+1][0]<=spans[i][1] for i in range(len(spans)-1))
    assert spans[-1][1]>=spans[-1][2]
    assert json.loads((directory/'case.json').read_text(encoding='utf-8'))['messages'][0]['text']==text
    assert {i for shot in r['images'] for i in shot['message_ids']}=={'long1','reply1'}
    print(json.dumps({'scroll_crops':len(spans),'same_message_id':True,'full_height_covered':True,'message_text_unchanged':True}))
