"""Copy paired historical generations into v2 review space; no source writes."""
from pathlib import Path
import sys
import hashlib
import json
import openpyxl

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from legalhub.synthesis import settings,read,write


def main():
    cfg,out=settings()
    name='projects/ScreenshotLegalBench_v2/generate_chat/output/wkinfo_samples_with_inference_2_5.xlsx'
    source=ROOT/name
    wb=openpyxl.load_workbook(source,read_only=True,data_only=True)
    sheet=wb.active;sheet.reset_dimensions();it=sheet.iter_rows(values_only=True);head=next(it)
    rows=[dict(zip(head,r)) for r in it];wb.close()
    for spec in cfg['cases']:
        if spec['language']!='zh':continue
        folder=out/'zh'/spec['id'];current=read(folder/'source.json');old=rows[spec['source_index']]
        if old['case_no']!=current['case_no']:raise ValueError('Paired baseline case number mismatch')
        baseline={'case_no':old['case_no'],'source_file':name,'source_index':spec['source_index'],
                  'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
                  'generation':old['inference_result'],
                  'historical_model':'not verified from workbook; do not infer from filename',
                  'human_score':None,'comparison_status':'paired case, not a scored model comparison'}
        write(folder/'legacy.baseline.json',baseline)
    print('Attached 3 historical Chinese generations for same-case review; no scores inferred.')


if __name__=='__main__':main()
