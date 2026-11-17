"""Prepare L06 native fixtures from author workbook by streaming XML; no model.
The complete 65 MB workbook is pinned; only two original sections are sampled.
Author saved predictions are comparison artifacts, not independent expert Gold.
"""
import ast,hashlib,json,sys,zipfile,xml.etree.ElementTree as ET
from pathlib import Path
HERE=Path(__file__).parent;ROOT=HERE.parents[2];sys.path.insert(0,str(HERE.parent))
from author_runtime import source

def main():
 folder,identity=source('legal_reasoning_paths');workbook=next((folder/'intances').glob('*.xlsx'))
 ns='{http://schemas.openxmlformats.org/spreadsheetml/2006/main}';selected=[]
 with zipfile.ZipFile(workbook) as z,z.open('xl/worksheets/sheet1.xml') as stream:
  for _,element in ET.iterparse(stream,events=['end']):
   if element.tag!=ns+'row':continue
   if int(element.attrib['r']) in (6,7):
    row={''.join(c for c in cell.attrib['r'] if c.isalpha()):''.join(cell.find(ns+'is').itertext()) if cell.find(ns+'is') is not None else '' for cell in element.findall(ns+'c')}
    selected.append(dict(worksheet_row=int(element.attrib['r']),document_path=row['B'],text=row['C'],original_edge_prompts={name:row[col] for name,col in [('provision_norm','D'),('norm_application','F'),('fact_application','H')]},author_saved_predictions={name:ast.literal_eval(row[col]) for name,col in [('provision_norm','E'),('norm_application','G'),('fact_application','I')]}))
   last=int(element.attrib['r']);element.clear()
   if last>=7:break
 request=dict(mode='native',language='ja',documents=[dict(id=selected[0]['document_path'],source_status='published_judgment',overview='',overview_status='not released in selected workbook rows',blocks=[dict(id='worksheet-row-'+str(r['worksheet_row']),text=r['text']) for r in selected])],exact_author_edge_tasks=[dict(stage=k,prompt=v) for k,v in selected[0]['original_edge_prompts'].items()])
 fixture=dict(request=request,evaluation_only=dict(author_saved_predictions=selected[0]['author_saved_predictions'],reference_status='author model outputs, not expert Gold',full_case_rebuilt=False,full_original_retrieval_executed=False),lineage=dict(source_commit=identity['commit'],workbook=workbook.relative_to(ROOT).as_posix(),workbook_sha256=hashlib.sha256(workbook.read_bytes()).hexdigest(),worksheet='sheet1',selected_rows=[6,7],full_workbook_downloaded=True,xml_streamed=True,original_text_modified=False,earlier_case_sections_not_reconstructed=True))
 (HERE/'native_input.json').write_text(json.dumps(fixture,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(dict(blocks=len(selected),characters=sum(len(r['text']) for r in selected),original_edge_tasks=3,model_requests=0)))
if __name__=='__main__':main()
