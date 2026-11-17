"""Read original archived Excel feedback; retain sheet, row and cell coordinates."""
from pathlib import Path
import io,json,zipfile,hashlib,sys
import openpyxl

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.restart_inventory import zip_name

OUT=ROOT/'datasets/v2.0.0/round_002/references'


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    archive=next(ROOT.glob('*.zip'));z=zipfile.ZipFile(archive)
    previous=ROOT/'datasets/v2.0.0/round_001'
    targets=[json.loads(p.read_text(encoding='utf-8')) for p in previous.glob('zh/*/source.json')]
    found=[];perfect=[];experiments=[]
    for info in z.infolist():
        name=zip_name(info)
        if name.startswith('__MACOSX') or not name.endswith('.xlsx'):continue
        if not any(t in name for t in ['案由泛化性测试','人工迭代实验','prompt迭代']):continue
        raw=z.read(info);sha=hashlib.sha256(raw).hexdigest()
        wb=openpyxl.load_workbook(io.BytesIO(raw),read_only=True,data_only=True)
        for sheet in wb:
            if sheet.title not in ['多版本汇总表','prompt_v3——v9','prompt_v0','Sheet3','prompt_v4','prompt_v5','数据表','假设']:continue
            sheet.reset_dimensions();iterator=sheet.iter_rows(values_only=True);header=list(next(iterator))
            for row_no,row in enumerate(iterator,2):
                obj=dict(zip(header,row));meta={'archive':archive.name,'workbook':name,'workbook_sha256':sha,'sheet':sheet.title,'excel_row':row_no}
                cells=[{'column':openpyxl.utils.get_column_letter(i+1),'label':header[i] if i<len(header) else None,'value':v} for i,v in enumerate(row) if v is not None]
                record={**meta,'cells':cells}
                for target in targets:
                    if obj.get('case_no')==target['case_no'] or obj.get('title')==target['title']:
                        found.append({**record,'case_id':target['id']})
                if sheet.title=='多版本汇总表' and obj.get('修正的5分完美剧本') and obj.get('修改要点'):
                    perfect.append(record)
                if '人工迭代实验' in name or ('prompt迭代' in name and any(obj.get(k) for k in ['优化方向','修改方向','insight结论'])):
                    experiments.append(record)
        wb.close()
    for filename,rows in [('same_case_feedback.json',found),('human_corrected_examples.json',perfect),('rubric_experiments.json',experiments)]:
        (OUT/filename).write_text(json.dumps(rows,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    print(json.dumps({'same_case_records':len(found),'human_corrected_examples':len(perfect),'rubric_experiments':len(experiments)},ensure_ascii=False))


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');main()
