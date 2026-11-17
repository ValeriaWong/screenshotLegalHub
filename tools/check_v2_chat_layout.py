"""Inspect nested card widths that outer-message clipping checks cannot detect."""
import sys,json,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.v2_cause_batch import OUT,read,save
from tools.render_v2_round2 import Browser

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,default=OUT);args=parser.parse_args()
    OUT=args.out.resolve()
    assert OUT.is_relative_to((ROOT/'datasets/v2.0.0').resolve())
    records=[]
    verification=read(OUT/'verification.json')
    identifiers=verification.get('rendered_case_ids') or [r['id'] for r in read(OUT/'manifest.json')['records']]
    with Browser('chrome-v2-layout-check') as browser:
        for ident in identifiers:
            directory=OUT/'zh'/ident
            for conv in read(directory/'case.json')['conversations']:
                browser.load(directory/(conv['id']+'.html'))
                cards=browser.evaluate('''Array.from(document.querySelectorAll('.transfer-bubble,.file-bubble,.picture-bubble'),x=>{
                    let b=x.getBoundingClientRect();return {id:x.closest('.row').dataset.id,x:b.x,width:b.width,
                    children:Array.from(x.querySelectorAll('.transfer-amount,.filename,.excerpt')).map(y=>{
                      let r=y.getBoundingClientRect();return {class:y.className,x:r.x,width:r.width,scrollWidth:y.scrollWidth,clientWidth:y.clientWidth};})};})''')
                for card in cards:
                    assert card['x']>=0 and card['x']+card['width']<=430,card
                    for child in card['children']:
                        assert child['x']>=card['x'] and child['x']+child['width']<=card['x']+card['width']+1,(card,child)
                        assert child['scrollWidth']<=child['clientWidth']+1,(card,child)
                transfer_labels=browser.evaluate('Array.from(document.querySelectorAll(".transfer-bubble"),x=>({id:x.closest(".row").dataset.id,label:x.querySelector(".transfer-label").textContent}))')
                messages={m['id']:m for m in read(directory/'case.json')['messages']}
                for mid,message in messages.items():
                    if message.get('conversation_id')!=conv['id']:continue
                    if message.get('minute_basis')=='not_visible':
                        stamps=browser.evaluate('Array.from(document.querySelectorAll(\'.row[data-id="'+mid+'"] .stamp\'),x=>x.textContent)')
                        assert all(not __import__('re').search(r'\d{1,2}:\d{2}',stamp) for stamp in stamps),(ident,mid,stamps)
                for transfer in transfer_labels:
                    receipt=messages[transfer['id']]['transfer'].get('receipt_status','not_reconstructed')
                    assert transfer['label']=={'expired':'已过期','received':'已被接收'}.get(receipt,'转账'),(ident,transfer)
                title=browser.evaluate('Array.from(document.querySelectorAll(".header .title-text,.header .subtitle"),x=>({text:x.textContent,width:x.clientWidth,scrollWidth:x.scrollWidth}))')
                records.append({'id':ident,'conversation_id':conv['id'],'cards':cards,'header':title,'transfer_labels':transfer_labels})
    save(OUT/'layout.verification.json',{'conversations':records,'nested_card_overflow':False})
    print(json.dumps({'conversations':len(records),'cards':sum(len(r['cards']) for r in records),'nested_card_overflow':False}))
