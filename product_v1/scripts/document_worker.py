"""Isolated MinerU worker. JSON stdin/stdout; no model calls or remote parsing.

Flash native text/Office parsing only. Scanned pages without embedded text are
reported explicitly. Installing OCR/VLM is a separate deployment decision.
"""
import contextlib
import importlib.metadata
import json
import sys
import uuid
from pathlib import Path

def run(p):
    source=Path(p['path'])
    if p['action']=='preview':
        import pypdfium2 as pdfium
        with pdfium.PdfDocument(str(source)) as pdf:
            if not 1<=p['page']<=len(pdf): raise ValueError('页码超出原件范围')
            page=pdf[p['page']-1]
            bitmap=page.render(scale=1.5)
            image=bitmap.to_pil()
            target=Path(p['target']);temporary=target.with_suffix('.'+uuid.uuid4().hex+'.tmp')
            image.save(temporary,format='PNG');temporary.replace(target)
            size=list(image.size);bitmap.close();page.close()
        return dict(size=size)
    if importlib.metadata.version('mineru')!='4.0.12' or importlib.metadata.version('docvortex')!='0.6.1': raise ValueError('Parser runtime version mismatch')
    from mineru.parser import MinerUParser
    from mineru.render import render, RenderFormat
    total=None
    options={}
    if source.suffix=='.pdf':
        import pypdfium2 as pdfium
        with pdfium.PdfDocument(str(source)) as pdf: total=len(pdf)
        start=p['start'];end=min(total,start+p['count'])
        if start>=total: return dict(items=[],total_pages=total,complete=True,producer=importlib.metadata.version('mineru'))
        options['page_range']=str(start+1)+'-'+str(end)
    parser=MinerUParser(tier='flash',parse_mode='txt',image_analysis=False)
    result=parser.parse(source,**options)
    content=render(result.middle_json,RenderFormat.CONTENT_LIST)
    if isinstance(content,str): content=json.loads(content)
    middle=result.to_dict()
    pages=[v['page_idx'] for v in middle.get('pages',[])]
    # Native Office pages are logical parse units, not Word/Excel print pagination.
    if total is None: total=max(pages,default=0)+1
    return dict(items=content,total_pages=total,complete=source.suffix!='.pdf' or end>=total,
                producer=importlib.metadata.version('mineru'),schema=middle.get('schema'),
                schema_version=middle.get('schema_version'),native=source.suffix!='.pdf',middle_json=middle)
if __name__=='__main__':
    try:
        payload=json.loads(sys.stdin.read())
        with contextlib.redirect_stdout(sys.stderr): result=run(payload)
        print(json.dumps(result,ensure_ascii=False))
    except Exception:
        print(json.dumps(dict(error='本地 MinerU 未能解析当前窗口；扫描页需要单独部署 OCR，Office 文件请检查是否损坏或加密'),ensure_ascii=False))
        sys.exit(0)
