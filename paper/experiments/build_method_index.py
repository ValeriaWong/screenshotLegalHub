"""Build the paper-facing navigation for independent method implementations and named evidence."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

REPO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REPO/'product_v1/backend/src'))
from screenshotlegal.method_reproductions.catalog import METHOD_MODULES,method_metadata

def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def relative(file,folder):
    return os.path.relpath(file,folder).replace(chr(92),'/')

def build(junit=None,equivalence=None):
    destination=REPO/'paper/method_reproductions';destination.mkdir(exist_ok=True)
    studies=[]
    for planned in sorted((REPO/'paper/experiments/results').rglob('planned_tasks.json')):
        directory=planned.parent
        index=directory/'methods/index.json'
        if not index.exists():continue
        methods=json.loads(index.read_text(encoding='utf-8'))['methods']
        manifest=directory/'manifest.lock.json'
        model=json.loads(manifest.read_text(encoding='utf-8')).get('model_id') if manifest.exists() else None
        studies.append(dict(directory=directory,model='demo' if model=='demo' else 'real_model' if model else 'unknown',methods=methods))
    cases=ET.parse(junit).getroot().findall('.//testcase') if junit else []
    parity=json.loads(Path(equivalence).read_text(encoding='utf-8')) if equivalence else {}
    entries=[]
    for method,name in METHOD_MODULES.items():
        meta=method_metadata(method);folder=destination/name;folder.mkdir(exist_ok=True)
        source=REPO/meta['implementation_file'];evidence=[]
        for study in studies:
            entry=next((m for m in study['methods'] if m['method_id']==method),None)
            if entry:
                evidence.append(dict(study=relative(study['directory'],REPO/'paper/experiments/results'),kind=study['model'],
                    statuses=entry['statuses'],planned=entry['planned'],
                    report=relative(study['directory']/entry['report'],folder),
                    named_directory=relative(study['directory']/'methods'/name,folder)))
        tests=[]
        for case in cases:
            test_name=case.attrib.get('name','')
            native_check=case.attrib.get('classname','').endswith('test_author_benchmark_adapter') and ((method=='E01' and 'react' in test_name) or (method=='E05' and 'react' not in test_name))
            budget_check=method in {'E01','E05'} and case.attrib.get('classname','').endswith('test_author_pilot_budget')
            if '['+name+']' not in test_name and not native_check and not budget_check:continue
            status='failed' if case.find('failure') is not None or case.find('error') is not None else 'skipped' if case.find('skipped') is not None else 'passed'
            tests.append(dict(name=case.attrib['name'],status=status,time_s=case.attrib.get('time')))
        if junit or equivalence:
            write(folder/(name+'.tests.json'),dict(
                reproduction_name=name,implementation_status=meta['implementation_status'],
                unit_checks=tests,behavior_equivalence=[r for r in parity.get('rows',[]) if r['method_id']==method],
                junit_source=relative(Path(junit),folder) if junit else None,
                junit_sha256=hashlib.sha256(Path(junit).read_bytes()).hexdigest() if junit else None,
                method_source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                note='Dispatch/header checks, offline equivalence and saved run states are distinct from legal-quality evaluation.'))
        write(folder/(name+'.index.json'),dict(meta,evidence=evidence))
        lines=['# '+name,'',f"候选编号：{method}；状态：{meta['implementation_status']}；复现程度：{meta['reproduction_level']}。",'',
               meta['reproduction_scope'],'',
               '原论文 benchmark 复现：未完成。implemented 仅指本项目工作流有代码；原任务、输入输出、创新点与适配阻塞请先读 METHOD.md。','',
               '[原任务与适配说明](METHOD.md) · [独立实现文件]('+relative(source,folder)+') · [按名称保存的工程测试]('+name+'.tests.json) · [机器可读索引]('+name+'.index.json)','','## 论文出处','']
        if meta['paper_sources']:
            for paper in meta['paper_sources']:
                lines += ['- '+paper['reference']+' '+' '.join('[来源]('+url+')' for url in paper['sources'])]
        else:lines += ['通用基线，无单篇对应论文。']
        lines += ['','## 已保存的实验','',
                  '以下批次可能采用不同代码、配置及输入，不能合并计算方法优势。原始执行版本以每份 record/provenance 和所在批次 implementation/ 为准；当前源码链接仅用于导航。',
                  '','| 批次 | 类型 | 状态 | 记录 |','|---|---|---|---|']
        for record in evidence:
            lines.append(f"| {record['study']} | {record['kind']} | {record['statuses']} | [按名称查看]({record['report']}) |")
        if not evidence:lines += ['| 尚无运行记录 | — | — | — |']
        if method in {'E01','E05'}:lines += ['', '[作者控制器适配与当前原任务状态](../../author_reproductions/'+('react' if method=='E01' else 'self_refine')+'/README.md) · [KIE/全图VQA当前冻结计划](../../author_reproductions/results/2026-10-28-kie-global-vqa/current_plan.json)']
        lines += ['','每项运行目录包含以 '+name+' 开头的 prompts、model_responses、output、tools、sources、test_results、record 和 provenance 文件。',
                  '完整性/字符范围通过不等于法律质量通过；未实现方法的登记/拒绝执行测试通过也不表示方法已实现。','']
        (folder/'README.md').write_text('\n'.join(lines),encoding='utf-8')
        entries.append(dict(meta,documentation=name+'/README.md',evidence=evidence))
    write(destination/'index.json',dict(method_count=len(entries),methods=entries))
    lines=['# 按方法名称查看复现代码与实验记录','',
           '从本目录进入每个方法，可以看到独立源码、文件头的论文出处与复现范围、原始回复、最终输出和测试记录。代码统一在 product_v1/backend/src/screenshotlegal/method_reproductions/，案件产品与论文批处理共用run(context)；KIE/全图VQA作者适配入口是同名文件的run_task。',
           '',
           '原清单有 51 个文献条目，本页是其中 21 个实验配置，不是 21 篇已复现论文。现有可调用配置16个、未实现5个；E05案件主链及E01/E05的KIE/全图VQA已接作者控制器，真实新增试跑待授权。作者原benchmark完整复现仍为0；逐项状态见author_reproductions。',
           '',
           '| 编号 | 复现名称 / 入口 | 状态 | 程度 |','|---|---|---|---|']
    lines += [f"| {m} | [{METHOD_MODULES[m]}]({METHOD_MODULES[m]}/README.md) | {method_metadata(m)['implementation_status']} | {method_metadata(m)['reproduction_level']} |" for m in METHOD_MODULES]
    lines += ['','## 文件组织','',
              '每批实验：paper/experiments/results/<批次>/methods/<复现名称>/。方法级 REPORT.md/test_results.json 汇总该批全部任务；runs/<案件组>__<任务ID>/ 中保存每次运行的命名文件，保留失败与重复，避免覆盖。',
              '',
              '旧 attempts/<哈希>.json 仍可读取；命名副本的 provenance.json 记录原文件位置和 SHA256。网页下载为 <复现名称>.<运行ID>.json。',
              '',
              '[原任务/适配逐项审查](../author_reproductions/ADAPTATION_REVIEW.md) · [51 条文献覆盖表](../author_reproductions/PAPER_COVERAGE.md) · [作者原代码运行](../author_reproductions/README.md) · [实验运行说明](../experiments/README.md)',
              '',
              '刷新本导航：python -B paper/experiments/build_method_index.py。需要更新工程测试入口时，同时提供 --junit 和 --equivalence 对应的已执行记录。','']
    (destination/'README.md').write_text('\n'.join(lines),encoding='utf-8')
    return dict(methods=len(entries),studies=len(studies),model_requests_created=0)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--junit',type=Path);parser.add_argument('--equivalence',type=Path)
    args=parser.parse_args();print(json.dumps(build(args.junit,args.equivalence),ensure_ascii=False))
