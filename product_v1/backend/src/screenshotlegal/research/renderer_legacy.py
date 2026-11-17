"""Revision-bound PNG/bbox renderer with atomic files and per-page checkpoints."""
import os
import io
from functools import lru_cache
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, __version__ as PILLOW_VERSION
from .contracts import digest, dumps
RENDERER = 'pillow-chat.v3'

class RenderLayoutError(ValueError):
    pass

def atomic_write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    with temporary.open('wb') as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temporary, path)

def font(size):
    for file in ['C:/Windows/Fonts/msyh.ttc','C:/Windows/Fonts/simhei.ttf',
                 '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc',
                 '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
                 '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']:
        if Path(file).exists():
            return ImageFont.truetype(file, size)
    return ImageFont.load_default(size=size)

@lru_cache(maxsize=32)
def font_signature(size):
    font_path=Path(getattr(font(size),'path',''))
    return dict(pillow_version=PILLOW_VERSION,font_file=font_path.name,
                font_sha256=digest(font_path.read_bytes()) if font_path.is_file() else None)

def wrap(text, f, width):
    lines = []
    for paragraph in text.split('\n'):
        line = ''
        for char in paragraph:
            if line and f.getlength(line+char)>width:
                lines.append(line)
                line = ''
            line += char
        lines.append(line)
    return lines

def layout(content, params):
    width, height, size = params['width'], params['page_height'], params['font_size']
    f = font(size)
    rows = content['messages'] or [dict(id='source',speaker='来源 / 校正版',timestamp=None,text=content['source_text'] or content['title'])]
    pages, blocks, y = [], [], 100
    for row in rows:
        header = row['speaker'] + (' · '+row['timestamp'] if row.get('timestamp') else '')
        lines = wrap(row['text'], f, width-110)
        while lines:
            capacity = (height-50-y-55)//(size+10)
            if capacity<1:
                pages.append(blocks); blocks=[]; y=100
                continue
            chunk, lines = lines[:capacity], lines[capacity:]
            h = 45+len(chunk)*(size+10)
            blocks.append(dict(message_id=row['id'],bbox=[30,y,width-30,y+h],header=header,lines=chunk))
            y += h+22
            if lines:
                pages.append(blocks); blocks=[]; y=100
    if blocks:
        pages.append(blocks)
    return pages


def fixed_layout(content, params, pages):
    """Reflow text inside saved regions; never silently clip text or move locked boxes."""
    from .geometry import validate
    pages=validate(pages,content)
    output=[dict(page=p['page'],width=p['width'],height=p['height'],
                 blocks=[dict(message_id=b['message_id'],bbox=b['bbox'],header='',lines=[]) for b in p['boxes']]) for p in pages]
    assigned={}
    for p in output:
        for b in p['blocks']:
            assigned.setdefault(b['message_id'],[]).append(b)
    for row in content['messages']:
        boxes=assigned.get(row['id'],[])
        if not boxes:
            continue
        chosen=None
        for size in range(params['font_size'],15,-1):
            f=font(size)
            width=min(b['bbox'][2]-b['bbox'][0]-16 for b in boxes)
            lines=wrap(row['text'],f,width)
            capacities=[max(0,int((b['bbox'][3]-b['bbox'][1]-16-(22 if b['bbox'][3]-b['bbox'][1]>=70 else 0))//(size+5))) for b in boxes]
            if width>=size and sum(capacities)>=len(lines):
                chosen=(size,lines,capacities)
                break
        if chosen is None:
            raise RenderLayoutError('消息 '+row['id']+' 的文本超出坐标框；已保留文字，请解锁并扩大框后重新保存')
        size,lines,capacities=chosen
        for b,capacity in zip(boxes,capacities):
            b['font_size']=size
            b['fixed']=True
            b['header']=row['speaker']+(' · '+row['timestamp'] if row.get('timestamp') else '')
            b['lines'],lines=lines[:capacity],lines[capacity:]
    missing=[m for m in content['messages'] if m['id'] not in assigned]
    if missing:
        extra=layout(dict(content,messages=missing),params)
        start=max([p['page'] for p in output],default=0)
        output.extend(dict(page=start+i,width=params['width'],height=params['page_height'],blocks=blocks) for i,blocks in enumerate(extra,1))
    for page in output:
        blocks=page['blocks']
        for i,a in enumerate(blocks):
            for other in blocks[i+1:]:
                ax,ay,bx,by=a['bbox'];cx,cy,dx,dy=other['bbox']
                overlap=max(0,min(bx,dx)-max(ax,cx))*max(0,min(by,dy)-max(ay,cy))
                if overlap>0:
                    raise RenderLayoutError('消息框重叠会遮挡正文；请移动或缩小坐标框后保存')
    return output

def render_png(content, params, blocks, page_number, background=None):
    image = Image.open(background).convert('RGB') if background else Image.new('RGB',(params['width'],params['page_height']),'#f3f5f8')
    d = ImageDraw.Draw(image)
    if background:
        for page in content.get('original_layout',[]):
            if page['page']==page_number:
                for region in page['boxes']: d.rectangle(region['bbox'],fill='white')
    f = font(params['font_size'])
    small = font(max(14,params['font_size']-6))
    title = '校正版派生视图' if content['kind']=='original' else '合成研究样本'
    if not background:
        d.text((30,20),title+' · '+str(page_number),font=small,fill='#536378')
        d.text((30,48),content['platform']+' · '+content['title'][:32],font=small,fill='#182b43')
    for block in blocks:
        x1,y1,x2,y2 = block['bbox']
        d.rounded_rectangle((x1,y1,x2,y2),radius=12,fill='white',outline='#d6dee8')
        if not block.get('fixed'):
            d.text((x1+12,y1+8),block['header'][:50],font=small,fill='#536378')
        if block.get('fixed'):
            # Clear the standard header; a short region has room only for message text.
            d.rounded_rectangle((x1,y1,x2,y2),radius=min(12,(y2-y1)/4),fill='white',outline='#d6dee8')
            size=block['font_size']; header_height=22 if y2-y1>=70 else 0
            if header_height:
                header_font=font(min(14,size))
                title=wrap(block['header'],header_font,max(8,x2-x1-16))[0]
                d.text((x1+8,y1+5),title,font=header_font,fill='#536378')
            for i,line in enumerate(block['lines']):
                d.text((x1+8,y1+8+header_height+i*(size+5)),line,font=font(size),fill='#182b43')
        else:
            for i,line in enumerate(block['lines']):
                d.text((x1+12,y1+38+i*(params['font_size']+10)),line,font=f,fill='#182b43')
    data = io.BytesIO()
    image.save(data,format='PNG')
    return data.getvalue()

def verified(root, asset):
    p = (Path(root)/asset['path']).resolve()
    if not p.is_relative_to(Path(root).resolve()) or not p.is_file() or digest(p.read_bytes())!=asset['sha256']:
        raise ValueError('Asset missing or failed SHA256 verification')
    return p

async def render_revision(store, job, checkpoint, alive):
    p = job['payload']
    revision, params = p['revision'],p['render']
    content = revision['content']
    role=content.get('visual_role','auto')
    if role=='auto': role='original' if content['kind']=='original' and content['original_assets'] else 'synthetic_render'
    originals=[store.get('review.asset',a['id'],job['owner']) for a in content['original_assets']]
    if role=='original':
        from .geometry import validate
        source_layout=validate(revision.get('layout') or content.get('original_layout',[]),content)
        mapped={p['page']:p for p in source_layout}
        if set(mapped)-set(range(1,len(originals)+1)): raise RenderLayoutError('原图坐标引用了不存在的页面')
        assets=[]
        for i,a in enumerate(originals,1):
            await alive();verified(store.root,a)
            page=mapped.get(i)
            if page and (page['width'],page['height'])!=(a['width'],a['height']): raise RenderLayoutError('原图坐标尺寸不一致')
            assets.append(dict(a,page=i,boxes=page['boxes'] if page else [],coordinate_space='pixels_xyxy',asset_role='original'))
        if not assets: raise RenderLayoutError('原图资产缺失，不能用占位派生图替代')
        return build_manifest(store,revision,params,assets,role)
    pages = fixed_layout(content,params,revision['layout']) if revision.get('layout') else [dict(page=i,width=params['width'],height=params['page_height'],blocks=blocks) for i,blocks in enumerate(layout(content,params),1)]
    assets = []
    for page in pages:
        number,blocks=page['page'],page['blocks']
        page_params=dict(params,width=page['width'],page_height=page['height'])
        await alive()
        key = str(number)
        old = job['checkpoints'].get(key)
        if old and old.get('render_policy')=='visual.v1':
            try:
                verified(store.root,old)
                assets.append(old)
                continue
            except ValueError:
                pass
        background=verified(store.root,originals[number-1]) if role=='transcription_overlay' and number<=len(originals) else None
        if background and Image.open(background).size!=(page['width'],page['height']): raise RenderLayoutError('派生视图与原图尺寸不一致')
        data = render_png(content,page_params,blocks,number,background)
        sha = digest(data)
        relative = 'assets/'+revision['sample_id']+'/'+str(revision['number'])+'/'+digest(params)[:16]+'/'+sha+'.png'
        atomic_write(store.root/relative,data)
        asset = dict(id=sha,path=relative,sha256=sha,width=page['width'],height=page['height'],
                     mime_type='image/png',page=number,boxes=[{k:v for k,v in b.items() if k in ['message_id','bbox']} for b in blocks],
                     coordinate_space='pixels_xyxy')
        asset['render_policy']='visual.v1'
        asset['asset_role']=role
        asset['font_sizes']=[b.get('font_size',params['font_size']) for b in blocks]
        await checkpoint(key,asset,'rendering')
        assets.append(asset)
    return build_manifest(store,revision,params,assets,role)

def build_manifest(store,revision,params,assets,role):
    content=revision['content']
    manifest = dict(contract='research.v2',renderer_version=RENDERER,requested_renderer_version=revision.get('renderer_version',RENDERER),revision=revision['number'],
                    sample_id=revision['sample_id'],text_hash=revision['content_hash'],parameters=params,
                    parameters_hash=digest(params),pages=assets,kind='derived' if content['kind']=='original' else 'synthetic')
    if role!='original':
        expected={m['id'] for m in content['messages']}
        actual={b['message_id'] for p in assets for b in p['boxes']}
        if expected-actual: raise RenderLayoutError('渲染缺少消息坐标映射')
    manifest['visual_role']=role
    manifest['validation']=dict(valid=True,policy='visual.v1',min_font_size=16 if role!='original' else None,coverage='original_asset_verified' if role=='original' else 'text_and_geometry',unannotated=role=='original' and not any(p['boxes'] for p in assets))
    manifest['layout_hash']=digest(revision.get('layout',[]))
    manifest['environment'] = font_signature(params['font_size'])
    manifest['sha256'] = digest(manifest)
    atomic_write(store.root/('manifests/'+manifest['sha256']+'.json'),dumps(manifest).encode())
    return manifest
