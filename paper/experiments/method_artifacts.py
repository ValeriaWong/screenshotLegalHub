"""Named method artifacts, with read compatibility for the original hash-only layout.

This module only reads/writes saved data; it never creates model requests.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
from screenshotlegal.method_reproductions.catalog import METHOD_MODULES

LAYOUT_VERSION='named-method-artifacts.v1'

def write_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def task_directory(out,task):
    name=METHOD_MODULES[task['method_id']]
    task_id=task['task_id']
    if not isinstance(task_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,200}',task_id):
        raise ValueError('Invalid artifact task ID')
    case=re.sub(r'[^A-Za-z0-9_-]+','-',str(task.get('case_group_id','case'))).strip('-')[:60] or 'case'
    return Path(out)/'methods'/name/'runs'/(case+'__'+task_id)

def record_file(out,task):
    return task_directory(out,task)/(METHOD_MODULES[task['method_id']]+'.record.json')

def saved_record_file(out,task):
    named=record_file(out,task)
    legacy=Path(out)/'attempts'/(task['task_id']+'.json')
    return named if named.exists() else legacy if legacy.exists() else None

def read_record(out,task):
    file=saved_record_file(out,task)
    return json.loads(file.read_text(encoding='utf-8')) if file else None

def save_record(out,task,record,original_file=None):
    """Preserve the full record and publish explicitly named views of its contents."""
    out=Path(out);directory=task_directory(out,task);name=METHOD_MODULES[task['method_id']]
    directory.mkdir(parents=True,exist_ok=True);target=record_file(out,task)
    if original_file is not None:
        original_file=Path(original_file)
        if original_file.resolve()!=target.resolve():target.write_bytes(original_file.read_bytes())
    else:
        write_json(target,record)
    result=record.get('result') or {};run=result.get('run') or {}
    provenance_file=directory/(name+'.provenance.json')
    old=json.loads(provenance_file.read_text(encoding='utf-8')) if provenance_file.exists() else {}
    provenance=dict(layout_version=LAYOUT_VERSION,method_id=task['method_id'],reproduction_name=name,
                    executed_method=run.get('method'),run_id=record.get('run_id'),
                    implementation_snapshot='implementation/',implementation_hashes='implementation.sha256.json',
                    note='The name is a directory label; executed_method retains the original frozen execution metadata.')
    if original_file is not None and original_file.resolve()!=target.resolve():
        provenance['original_record']=str(original_file.relative_to(out)).replace(chr(92),'/')
        provenance['original_record_sha256']=hashlib.sha256(original_file.read_bytes()).hexdigest()
    elif old.get('original_record'):
        provenance.update({k:old[k] for k in ['original_record','original_record_sha256']})
    provenance['record_sha256']=hashlib.sha256(target.read_bytes()).hexdigest()
    write_json(provenance_file,provenance)
    write_json(directory/(name+'.prompts.json'),[
        dict(stage=s['stage'],status=s['status'],messages=s.get('messages'),model_parameters=s.get('model_parameters'))
        for s in result.get('steps',[])])
    write_json(directory/(name+'.model_responses.json'),[
        dict(stage=s['stage'],status=s['status'],response=s.get('response'),error=s.get('error'))
        for s in result.get('steps',[])])
    write_json(directory/(name+'.output.json'),dict(reproduction_name=name,method_id=task['method_id'],
        run_id=record.get('run_id'),status=record['status'],output=run.get('output'),error=run.get('error') or record.get('error')))
    write_json(directory/(name+'.tools.json'),result.get('tools',[]))
    write_json(directory/(name+'.sources.json'),result.get('sources',[]))
    write_json(directory/(name+'.test_results.json'),dict(reproduction_name=name,status=record['status'],
        usage=run.get('usage'),engineering_metrics=run.get('engineering_metrics'),scoring=record.get('scoring'),
        note='Execution and quote-span checks do not establish legal or semantic accuracy.'))
    return target

def publish_methods(out,tasks,rows,method_statistics=None):
    out=Path(out);statistics={r['method']:r for r in method_statistics or []};entries=[]
    row_index={r['task_id']:r for r in rows}
    for method in dict.fromkeys(t['method_id'] for t in tasks):
        name=METHOD_MODULES[method];directory=out/'methods'/name
        selected_tasks=[t for t in tasks if t['method_id']==method]
        selected=[row_index[t['task_id']] for t in selected_tasks]
        write_json(directory/(name+'.planned_tasks.json'),selected_tasks)
        for task,row in zip(selected_tasks,selected):
            original=saved_record_file(out,task)
            # Reports add scoring to a loaded view; never rewrite that into the raw record.
            if original:save_record(out,task,row,original_file=original)
        stats=statistics.get(method) or dict(method=method,planned=len(selected),
            statuses=dict(Counter(r['status'] for r in selected)),
            model_calls=sum((r.get('result',{}).get('run',{}).get('usage') or {}).get('model_calls',0) for r in selected))
        write_json(directory/(name+'.test_results.json'),dict(stats,reproduction_name=name))
        records=[]
        for task,row in zip(selected_tasks,selected):
            path=record_file(out,task)
            records.append(dict(task_id=task['task_id'],case_group_id=task.get('case_group_id'),status=row['status'],
                record=str(path.relative_to(out)).replace(chr(92),'/') if path.exists() else None))
        write_json(directory/(name+'.index.json'),dict(layout_version=LAYOUT_VERSION,method_id=method,
            reproduction_name=name,records=records))
        lines=['# '+name,'',f"Method: {method}. Planned: {len(selected)}. Statuses: {dict(Counter(r['status'] for r in selected))}.",'',
               'Original run metadata and failures are preserved. This is not a legal-quality score.','',
               '| Case group | Status | Record |','|---|---|---|']
        for record in records:
            file=record['record']
            link='[raw record]('+str(Path(file).relative_to(Path('methods')/name)).replace(chr(92),'/')+')' if file else 'not started'
            case=str(record.get('case_group_id') or '').replace('|','\\|').replace('\n',' ')
            lines.append(f"| {case} | {record['status']} | {link} |")
        (directory/(name+'.REPORT.md')).write_text('\n'.join(lines)+'\n',encoding='utf-8')
        entries.append(dict(method_id=method,reproduction_name=name,planned=len(selected),statuses=dict(Counter(r['status'] for r in selected)),
                            report='methods/'+name+'/'+name+'.REPORT.md'))
    write_json(out/'methods/index.json',dict(layout_version=LAYOUT_VERSION,methods=entries))
    lines=['# 按方法名称查看实验记录','','本目录由已保存的记录生成；没有发出模型请求。原始代码快照、失败及任务分母保留。','',
           '| 方法 | 名称 | 计划数 | 状态 | 报告 |','|---|---|---:|---|---|']
    lines += [f"| {r['method_id']} | {r['reproduction_name']} | {r['planned']} | {r['statuses']} | [查看]({r['report']}) |" for r in entries]
    (out/'METHODS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return entries

def organize_existing(out):
    """Add named copies/indexes without changing old records, reports or code archives."""
    out=Path(out);tasks=json.loads((out/'planned_tasks.json').read_text(encoding='utf-8'));rows=[]
    for task in tasks:
        legacy=out/'attempts'/(task['task_id']+'.json')
        original=legacy if legacy.exists() else saved_record_file(out,task)
        row=json.loads(original.read_text(encoding='utf-8')) if original else dict(task,status='not_started')
        if original:save_record(out,task,row,original_file=original)
        rows.append(row)
    old_report=out/'report.json'
    statistics=json.loads(old_report.read_text(encoding='utf-8')).get('methods',[]) if old_report.exists() else []
    entries=publish_methods(out,tasks,rows,statistics)
    return dict(out=str(out),methods=len(entries),tasks=len(tasks),statuses=dict(Counter(r['status'] for r in rows)),
                model_requests_created=0)
