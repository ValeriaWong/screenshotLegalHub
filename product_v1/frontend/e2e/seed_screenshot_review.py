import os,json,io
from pathlib import Path
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from PIL import Image,ImageDraw,ImageFont
from screenshotlegal.settings import Settings
from screenshotlegal.api.main import create_app
from screenshotlegal.research.screenshot_review import project
from screenshotlegal.research.contracts import digest
root=Path(__file__).resolve().parents[3]
settings=Settings(data_dir=Path(os.environ['DATA_DIR']),host='127.0.0.1')
command.upgrade(Config(str(root/'product_v1/backend/alembic.ini')),'head')
app=create_app(settings)
with TestClient(app) as client:
    response=client.post('/v1/auth/setup',json=dict(username='e2eadmin',password='e2e-synthetic-password-123',display_name='审核验证'))
    if response.status_code!=200:
        response=client.post('/v1/auth/login',json=dict(username='e2eadmin',password='e2e-synthetic-password-123'))
    owner=client.get('/v1/auth/me').json()['id']
    store=app.state.research['store']
    panel=app.state.research['screenshot_review']
    for dataset,count in [('A',3),('B',1)]:
        items=[]
        for i in range(1,count+1):
            image=Image.new('RGB',(760,1080),'#ededed');d=ImageDraw.Draw(image)
            font_path=Path('C:/Windows/Fonts/msyh.ttc')
            font=ImageFont.truetype(str(font_path),25) if font_path.exists() else ImageFont.load_default(size=25)
            d.rectangle((0,0,760,110),fill='#f7f7f7')
            d.text((325,42),'聊天',font=font,fill='#202020')
            d.text((270,150),'今天 10:01',font=font,fill='#777777')
            for y,side,txt in [(220,'left','我们商量一下还款吧。'),(350,'right','收到，我来安排。')]:
                x=90 if side=='left' else 345
                d.rounded_rectangle((x,y,x+325,y+85),radius=10,fill='white' if side=='left' else '#a9e879')
                d.text((x+15,y+24),txt,font=font,fill='#202020')
                d.rounded_rectangle((20 if side=='left' else 690,y,70 if side=='left' else 740,y+50),radius=5,fill='#8e9ca4')
            d.text((220,980),'测试用合成截图 · '+dataset+str(i),font=font,fill='#777777')
            out=io.BytesIO();image.save(out,format='PNG');data=out.getvalue();sha=digest(data)
            rel='originals/'+sha+'.png';(store.root/'originals').mkdir(exist_ok=True);(store.root/rel).write_bytes(data)
            raw=dict(dialog_name='聊天',provenance={'test':True},conversation=[
                dict(speaker='甲',content='我们商量一下还款吧。',timestamp='10:01',side='left',message_bbox={'min_x':90,'min_y':220,'max_x':415,'max_y':305},image='',transfer=[],file=[],custom={'keep':'value'}),
                dict(speaker='乙',content='收到，我来安排。',timestamp=None,side='right',message_bbox={'min_x':345,'min_y':350,'max_x':670,'max_y':435},image='',transfer=[{'amount':200,'currency':'CNY'}],file=[])])
            items.append(dict(id=dataset.lower()+str(i).zfill(3),dataset=dataset,original_json=raw,message_path=['conversation'],messages=project(raw,['conversation']),speakers=['甲','乙'],
                              source_ref='test-fixture',source_sha256=digest(raw),annotation_level='unverified' if dataset=='A' else 'synthetic',
                              judgment_excerpt='双方通过微信协商还款。',asset=dict(path=rel,sha256=sha,width=760,height=1080,mime_type='image/png')))
        if not panel.state(owner,dataset)['items']:
            panel.initialize(owner,dataset,items,dict(annotation_level='unverified' if dataset=='A' else 'synthetic',source_id='test-fixture'),0)
print('isolated QA dataset ready')
