"""Isolated vendor entry; stdout is one JSON object, diagnostics are not exposed."""
import contextlib
import importlib.metadata
import json
import sys
from pathlib import Path

def docling(source):
    from docling.datamodel.document import InputDocument
    from docling.datamodel.base_models import InputFormat
    from docling.backend.msword_backend import MsWordDocumentBackend
    from docling.backend.msexcel_backend import MsExcelDocumentBackend
    from docling.backend.mspowerpoint_backend import MsPowerpointDocumentBackend
    from docling.backend.csv_backend import CsvDocumentBackend
    from docling_core.types.doc import TableItem
    classes={'.docx':(InputFormat.DOCX,MsWordDocumentBackend),'.xlsx':(InputFormat.XLSX,MsExcelDocumentBackend),
             '.pptx':(InputFormat.PPTX,MsPowerpointDocumentBackend),'.csv':(InputFormat.CSV,CsvDocumentBackend)}
    kind,backend=classes[source.suffix]
    original=InputDocument(path_or_stream=source,format=kind,backend=backend)
    try:
        document=original._backend.convert()
        rows=[]
        for item,level in document.iterate_items():
            label=str(getattr(item.label,'value',item.label));provenance=getattr(item,'prov',[]) or []
            row=dict(type='table' if isinstance(item,TableItem) else label,text=getattr(item,'text',''),
                     page_idx=max(0,provenance[0].page_no-1) if provenance else 0,source_ref=item.self_ref,
                     parent_id=item.parent.cref if item.parent else None,children=[c.cref for c in item.children])
            if isinstance(item,TableItem):row['table_body']=item.export_to_html(doc=document)
            # Office coordinates can be slide/sheet layout, not physical print pages.
            # Keep them in the vendor artifact; do not overlay them on a PDF page.
            rows.append(row)
        return dict(items=rows,total_pages=max((r['page_idx'] for r in rows),default=0)+1,complete=True,
                    producer='docling-slim-'+importlib.metadata.version('docling-slim'),schema='docling-native',
                    middle_json=document.export_to_dict())
    finally:original._backend.unload()

def paddle(source,p):
    from paddleocr import PPStructureV3
    import pypdfium2 as pdfium
    from tempfile import TemporaryDirectory
    pipeline=PPStructureV3(use_doc_orientation_classify=False,use_doc_unwarping=False,
                         use_textline_orientation=False,use_seal_recognition=False,
                         use_formula_recognition=False,use_table_recognition=True)
    count=1
    if source.suffix=='.pdf':
        with pdfium.PdfDocument(str(source)) as pdf:count=len(pdf)
    end=min(count,p['start']+p['count']);rows=[];raw=[]
    with TemporaryDirectory() as temporary:
        for index in range(p['start'],end):
            page_path=source
            if source.suffix=='.pdf':
                with pdfium.PdfDocument(str(source)) as pdf:
                    page=pdf[index];bitmap=page.render(scale=1.5);image=bitmap.to_pil()
                    page_path=Path(temporary)/(str(index)+'.png');image.save(page_path)
                    width,height=image.size;bitmap.close();page.close()
            else:
                from PIL import Image
                with Image.open(source) as image:width,height=image.size
            for result in pipeline.predict(str(page_path)):
                data=result.json
                if isinstance(data,str):data=json.loads(data)
                data=data.get('res',data);raw.append(data)
                for block in data.get('parsing_res_list',[]):
                    box=block.get('block_bbox')
                    item=dict(type=block.get('block_label','text'),text=block.get('block_content',''),page_idx=index)
                    if item['type']=='table':item['table_body']=item.pop('text')
                    if box:item['bbox']=[box[0]/width*1000,box[1]/height*1000,box[2]/width*1000,box[3]/height*1000]
                    rows.append(item)
    return dict(items=rows,total_pages=count,complete=end>=count,producer='paddleocr-'+importlib.metadata.version('paddleocr'),middle_json=raw)

if __name__=='__main__':
    payload=json.loads(sys.stdin.read())
    try:
        with contextlib.redirect_stdout(sys.stderr):
            path=Path(payload['path'])
            result=docling(path) if payload['engine']=='docling' else paddle(path,payload)
        print(json.dumps(result,ensure_ascii=False))
    except Exception:
        print(json.dumps(dict(error='候选解析器不可用：请检查隔离依赖、本地模型和文件格式；原件及已有解析版本保留'),ensure_ascii=False))
