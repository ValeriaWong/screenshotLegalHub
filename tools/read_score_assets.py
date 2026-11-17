"""Read Feishu exports without modifying them; summarize score coverage."""
from pathlib import Path
from collections import Counter
import io,json,zipfile
import openpyxl
from tools.restart_inventory import zip_name
ROOT=Path(__file__).resolve().parents[1]
out=[]
with zipfile.ZipFile(next(ROOT.glob('*.zip'))) as z:
    e=next(e for e in z.infolist() if zip_name(e).endswith('.xlsx') and e.file_size>30_000_000)
    wb=openpyxl.load_workbook(io.BytesIO(z.read(e)),read_only=True,data_only=True)
    for s in wb:
        if 'v3' not in s.title:continue
        s.reset_dimensions();rows=list(s.iter_rows(values_only=True));header=rows[0];data=rows[1:]
        scores=[]
        for i,h in enumerate(header):
            if isinstance(h,str) and ('人工打分' in h and '理由' not in h and '异常' not in h):
                v=[r[i] for r in data if len(r)>i and r[i] is not None and str(r[i]).strip()]
                scores.append({'column':h,'non_empty':len(v),'value_distribution':dict(Counter(str(x) for x in v))})
        ci=header.index('case_no')
        cases=Counter(str(r[ci]) for r in data if len(r)>ci and r[ci] is not None)
        out.append({'workbook':zip_name(e),'sheet':s.title,'data_rows':len(data),'distinct_case_no':len(cases),'scores':scores})
    wb.close()
(ROOT/'reports/restart/human_score_coverage.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(out,ensure_ascii=False))
