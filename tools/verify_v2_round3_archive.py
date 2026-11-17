"""Compare primary, alternative and supplemental archives to the actual workbook."""
import sys
from pathlib import Path
import openpyxl
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.v2_cause_batch import OUT,SOURCE,ROOT,read,save,sha,processing_items

def main():
    wb=openpyxl.load_workbook(SOURCE,read_only=True,data_only=True);sheet=wb.active;sheet.reset_dimensions()
    iterator=sheet.iter_rows(values_only=True);header=next(iterator);rows=[dict(zip(header,r)) for r in iterator];wb.close()
    digest=sha(SOURCE.read_bytes());paths=[OUT/'zh'/i['id']/'source.json' for i in processing_items()]
    paths+=list((OUT/'zh').glob('*/alternatives/*/source.json'))
    checked=[]
    for path in paths:
        s=read(path);r=rows[s['source_index']]
        assert s['source_sha256']==digest
        assert s['text']==r['content'] and s['case_no']==r['case_no'] and s['cause']==r['case_cause']
        assert s['title']==r['title'] and s['url']==r['url']
        assert sha(s['text'].encode('utf-8'))==s['judgment_text_sha256']
        assert (path.parent/'judgment.txt').read_bytes()==r['content'].encode('utf-8')
        checked.append(s['source_index'])
    assert set(checked)==set(range(len(rows)))
    accepted=OUT/'zh/zh_0146';previous=ROOT/'datasets/v2.0.0/round_002/zh/zh_sales_146'
    old=read(previous/'render.json');new=read(accepted/'render.json')
    assert len(old['images'])==len(new['images'])==5
    for a,b in zip(old['images'],new['images']):
        assert sha((previous/a['path']).read_bytes())==sha((accepted/b['path']).read_bytes())
    result={'workbook_sha256':digest,'workbook_rows':len(rows),'archived_source_files_checked':len(paths),
        'all_350_rows_archived_and_exact':True,'accepted_round_002_images_unchanged':5,
        'source_fields_preserved':True,'quality_certified':False}
    save(OUT/'archive.verification.json',result);print(result)

if __name__=='__main__':main()
