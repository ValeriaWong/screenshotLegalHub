"""Archive unselected judgments without replacing the selected source."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.v2_cause_batch import OUT,SOURCE,ROOT,read,save,sha,paragraphs
import openpyxl

def main():
    wb=openpyxl.load_workbook(SOURCE,read_only=True,data_only=True)
    sheet=wb.active;sheet.reset_dimensions();rows=sheet.iter_rows(values_only=True)
    header=next(rows);records=[dict(zip(header,r)) for r in rows];wb.close()
    count=0
    for item in read(OUT/'manifest.json')['representatives']:
        for index in item['alternatives']:
            if index==item['source_index']:continue
            row=records[index];directory=OUT/'zh'/item['id']/'alternatives'/f'{index:04d}'
            source={'id':f"{item['id']}_alternative_{index:04d}",'parent_case_id':item['id'],
                'language':'zh','platform':'WeChat','jurisdiction':'China','cause':row['case_cause'],
                'case_no':row['case_no'],'title':row['title'],'url':row['url'],
                'source_index':index,'source_file':SOURCE.relative_to(ROOT).as_posix(),
                'source_sha256':sha(SOURCE.read_bytes()),'judgment_text_sha256':sha(row['content'].encode('utf-8')),
                'text':row['content'],'paragraphs':paragraphs(row['content']),
                'split':'development','status':'unselected_alternative_source_not_a_chat_candidate'}
            path=directory/'source.json'
            if path.exists():assert read(path)==source
            else:save(path,source)
            (directory/'judgment.txt').write_bytes(row['content'].encode('utf-8'))
            save(directory/'source.verification.json',{'excel_row':index+2,'court':row['court'],'date':row['date'],
                'source_sha256_expected':source['source_sha256'],'source_sha256_actual':source['source_sha256'],
                'content_exact':True,'judgment_text_sha256':source['judgment_text_sha256']})
            count+=1
    print({'alternative_judgments_archived':count})

if __name__=='__main__':main()
