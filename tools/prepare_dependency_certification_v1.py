"""Create blinded local review packets and audit the new synthetic pilot."""
import argparse
import hashlib
import json
import random
import shutil
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from build_dependency_pilot_v1 import ROLES, evaluate, subset_check, worlds


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read_lines(path):return [json.loads(s) for s in path.read_text(encoding='utf-8').splitlines()]
def put(path,value,lines=False):
    with path.open('x',encoding='utf-8',newline='\n') as f:
        if lines:
            for row in value:f.write(json.dumps(row,ensure_ascii=False)+'\n')
        else:json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n')


HTML='''<!doctype html><html lang="zh"><meta charset="utf-8"><title>证据子集独立复核</title>
<style>body{font:16px system-ui;margin:24px;background:#f4f5f7;color:#182230}main{max-width:1250px;margin:auto}button,select,input,textarea{font:inherit;padding:8px;border:1px solid #b8c0cb;border-radius:6px}button{cursor:pointer;background:white}#images{display:flex;gap:12px;overflow:auto;margin:18px 0}#images figure{margin:0;flex-shrink:0}#images img{width:215px;display:block;border:1px solid #ccd1d9}textarea{width:100%;box-sizing:border-box;min-height:88px;margin:8px 0}label{display:block;margin-top:12px}.bar{display:flex;gap:12px;align-items:center;flex-wrap:wrap}.card{background:white;padding:20px;border-radius:12px;margin:18px 0}small{color:#536273}#status{font-weight:600}</style>
<main><h1>证据子集独立复核</h1><p>这是虚构研究样本。只检查当前提供的材料，分别判断答案及证据限度。页面不提供作者答案或另一位复核者意见。数据只保存在当前浏览器；完成后导出 JSON。</p>
<div class="bar"><button onclick="move(-1)">上一项</button><select id="pick" onchange="load(Number(this.value))"></select><button onclick="move(1)">下一项</button><button onclick="download()">导出复核结果</button><span id="status"></span></div>
<div class="card"><small id="item"></small><p id="question"></p><div id="images"></div>
<label>判断 <select id="verdict" onchange="save()"><option value="pending">待复核</option><option value="satisfied">图示款项满足约定前提</option><option value="not_satisfied">已关联的图示款项/时序不满足</option><option value="not_established">材料不足以确定</option><option value="ambiguous_question">题目或条件有歧义，退回修改</option></select></label>
<label>可核查的身份/事项关联、金额与事件日期<textarea id="facts" oninput="save()"></textarea></label>
<label>支持、反证与缺证：标出 P0…及原句；说明缺少信息为什么影响答案<textarea id="evidence" oninput="save()"></textarea></label>
<label>问题范围与法律措辞是否合适；不要将条件判断扩大成真实法律责任<textarea id="scope" oninput="save()"></textarea></label></div>
<div class="bar"><label>复核者标识 <input id="reviewer" placeholder="姓名或内部编号" oninput="save()"></label><small>点击截图可查看原尺寸。导出后需另行汇总分歧，页面不会自动认证。</small></div></main>
<script>
const packet=__PACKET__;const key='dependency_review_'+packet.packet_id;let saved=JSON.parse(localStorage.getItem(key)||'{}');let index=0;
const $=id=>document.getElementById(id);packet.items.forEach((r,i)=>{let o=document.createElement('option');o.value=i;o.textContent=(i+1)+' · '+r.blind_id;$('pick').appendChild(o)});
function load(i){index=Math.max(0,Math.min(packet.items.length-1,i));let r=packet.items[index],v=saved[r.blind_id]||{};$('pick').value=index;$('item').textContent=r.blind_id+' · '+r.images.length+' 张图';$('question').textContent=r.question;$('images').replaceChildren();r.images.forEach((p,j)=>{let f=document.createElement('figure'),a=document.createElement('a'),img=document.createElement('img'),cap=document.createElement('figcaption');a.href=p;a.target='_blank';img.src=p;img.alt='P'+j;cap.textContent='P'+j;a.appendChild(img);f.append(a,cap);$('images').appendChild(f)});if(!r.images.length)$('images').textContent='本项没有提供截图。';for(let field of ['verdict','facts','evidence','scope'])$(field).value=v[field]||(field==='verdict'?'pending':'');$('reviewer').value=saved.reviewer||'';progress()}
function progress(){let n=packet.items.filter(r=>saved[r.blind_id]&&saved[r.blind_id].verdict!=='pending').length;$('status').textContent=n+'/'+packet.items.length+' 已记录'}
function save(){let r=packet.items[index];saved.reviewer=$('reviewer').value;saved[r.blind_id]={};for(let field of ['verdict','facts','evidence','scope'])saved[r.blind_id][field]=$(field).value;saved[r.blind_id].updated_at=new Date().toISOString();localStorage.setItem(key,JSON.stringify(saved));progress()}
function move(step){save();load(index+step)}function download(){save();let result={packet_id:packet.packet_id,reviewer:saved.reviewer||null,professional_signoff:false,automatic_certification:false,items:packet.items.map(r=>({blind_id:r.blind_id,image_hashes:r.image_hashes,...(saved[r.blind_id]||{verdict:'pending'})}))};let u=URL.createObjectURL(new Blob([JSON.stringify(result,null,2)],{type:'application/json'}));let a=document.createElement('a');a.href=u;a.download=packet.packet_id+'.review.json';a.click();setTimeout(()=>URL.revokeObjectURL(u),1000)}load(0);
</script></html>'''


def main():
    p=argparse.ArgumentParser();p.add_argument('--dataset',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    dataset=(ROOT/a.dataset).resolve();out=(ROOT/a.output).resolve();dataset.relative_to(ROOT);out.relative_to(ROOT)
    if out.exists():raise FileExistsError('Use a new output directory.')
    tasks={t['id']:t for t in read_lines(dataset/'tasks.image_only.jsonl')}
    reviews={r['id']:r for r in read_lines(dataset/'reviewer_only.certification_candidates.jsonl')}
    bindings=read_lines(dataset/'image_bindings.jsonl')
    protected={str(q.relative_to(ROOT)).replace('\\','/'):sha(q) for q in dataset.rglob('*') if q.is_file()}
    assert len(tasks)==12 and len(bindings)==48
    edges=[];packets=[];subset_count=0
    for ident,r in reviews.items():
        task=tasks[ident];universe=worlds(r['language'])
        for original in r['subset_checks']:
            calculated=subset_check(r['world'],r['language'],original['roles'],universe)
            assert calculated==original
            subset_count+=1
            indices=[i for i,role in enumerate(ROLES) if role in original['roles']]
            packets.append({'original_task_id':ident,'roles':original['roles'],'question':task['prompt'].split('\n',1)[0],
                'images':[task['images'][i] for i in indices],'image_hashes':[task['image_hashes'][i] for i in indices]})
        parent=r['counterfactual_parent']
        if parent:
            prior=reviews[parent]
            fields=[field for field in r['world'] if r['world'][field]!=prior['world'][field]]
            assert fields==r['changed_world_fields'] and len(fields)==1
            affected=[role for role in ROLES if r['observations_by_role'][role]!=prior['observations_by_role'][role]]
            assert len(affected)==1
            changed_images=[role for i,role in enumerate(ROLES) if task['image_hashes'][i]!=tasks[parent]['image_hashes'][i]]
            assert changed_images==affected
            edges.append({'parent':parent,'child':ident,'changed_field':fields[0],
                'changed_role':affected[0],'changed_image_count':1,
                'parent_reference_answer':prior['author_reference_answer'],
                'child_reference_answer':r['author_reference_answer'],
                'answer_changed':prior['author_reference_answer']!=r['author_reference_answer']})
    assert subset_count==192 and len(edges)==10 and all(e['answer_changed'] for e in edges)
    for b in bindings:
        assert sha(ROOT/b['image'])==b['sha256'] and [b['width'],b['height']]==[860,1864]
        for box in b['message_boxes']:
            x,y,w,h=box['bbox_pixels'];assert 0<=x<x+w<=860 and 0<=y<y+h<=1864
    out.mkdir(parents=True,exist_ok=False)
    image_dir=out/'review_images';image_dir.mkdir()
    for t in tasks.values():
        for image,digest in zip(t['images'],t['image_hashes']):
            dest=image_dir/(digest+'.png')
            if not dest.exists():shutil.copyfile(ROOT/image,dest)
    maps=[]
    for slot,seed in [('A',41201),('B',53109)]:
        shuffled=packets.copy();random.Random(seed).shuffle(shuffled);rows=[]
        for i,item in enumerate(shuffled,1):
            blind_id=f'{slot}{i:03d}'
            rows.append({'blind_id':blind_id,'question':item['question'],
                'images':['review_images/'+digest+'.png' for digest in item['image_hashes']],
                'image_hashes':item['image_hashes']})
            maps.append({'reviewer_slot':slot,'blind_id':blind_id,'task_id':item['original_task_id'],'roles':item['roles']})
        packet={'packet_id':f'dependency_pilot_v1_reviewer_{slot}','answers_withheld':True,'items':rows}
        put(out/f'packet_{slot}.blind.json',packet)
        with (out/f'review_{slot}.html').open('x',encoding='utf-8') as f:
            f.write(HTML.replace('__PACKET__',json.dumps(packet,ensure_ascii=False).replace('</','<\\/')))
    put(out/'blind_mapping.reviewer_only.jsonl',maps,lines=True)
    put(out/'counterfactual_edges.checked.jsonl',edges,lines=True)
    put(out/'verification.json',{'scenarios':12,'screenshots':48,'unique_pixel_images':len(list(image_dir.glob('*.png'))),
        'subset_checks_recomputed':192,'finite_worlds_per_language':len(worlds('zh')),
        'one_field_one_image_counterfactual_edges':10,'all_counterfactual_labels_change':True,
        'image_hashes_valid':True,'boxes_within_images':True,
        'reviewer_packets':2,'items_per_packet':192,'reviewer_answers_received':0,
        'semantic_certification':'pending','professional_legal_certification':'pending',
        'api_calls':0,'source_hashes':protected,
        'original_dataset_unchanged':all(sha(ROOT/path)==digest for path,digest in protected.items())})
    print(json.dumps({'output':str(out),'packets':2,'items_per_packet':192,'counterfactual_edges':10},ensure_ascii=False))


if __name__=='__main__':sys.stdout.reconfigure(encoding='utf-8');main()
