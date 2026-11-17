"""MetaGPT native QA continuation, Hong et al., arXiv:2308.00352.
Author v0.3.0 820fee5df6697b4e85e90c787940de111c3ed05b, QaEngineer /
WriteTest / RunCode.run / DebugError / Team / Role / Environment execute their
original bodies. Original input: Engineer code-path handoff + prior design message;
output: generated unittest files, real process output, routed feedback/test repairs.
This resumes the already generated README snake task AFTER the separately logged,
harness-selected author review; it is not a fresh all-autonomous startup run.
Benchmark scope: one software task, not HumanEval/MBPP/SoftwareDev scores.
Adaptations: Windows process executor uses this pinned Python, os.pathsep and UTF8;
original RunCode.run_script alone is replaced, while original run and QA routing
remain. Known upstream v0.3.0 limitation: Engineer watches WriteTasks only, so
RunCode failures addressed to Engineer do not implement automatic dev repair.
Original file-info eval is replaced by literal_eval on its own dictionary records.
No source/test manual edits, synthetic passes, local weights or expert legal Gold.
"""
import ast,asyncio,contextlib,hashlib,importlib,json,os,re,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from author_runtime import emit,tool
from loader import load


def install_qa(runtime,root):
    actions=sys.modules['metagpt.actions'];roles=runtime['roles'];executions=[]
    for name,file in [('WriteTest','write_test'),('RunCode','run_code'),('DebugError','debug_error')]:
        setattr(actions,name,getattr(importlib.import_module('metagpt.actions.'+file),name))
    qa_module=importlib.import_module('metagpt.roles.qa_engineer')
    qa_module.eval=ast.literal_eval
    QaEngineer=qa_module.QaEngineer;roles.QaEngineer=QaEngineer
    original_write=QaEngineer.write_file
    def write_file(self,filename,code):
        test_root=(self.get_workspace()/'tests').resolve();target=(test_root/filename).resolve()
        if not target.is_relative_to(test_root) or target.suffix!='.py':raise ValueError('QA output escapes isolated tests directory')
        return original_write(self,filename,code)
    QaEngineer.write_file=write_file
    async def run_script(cls,working_directory,additional_python_paths=None,command=None):
        cwd=Path(working_directory).resolve();workspace=(root/'workspace').resolve()
        if not cwd.is_relative_to(workspace):raise ValueError('QA command directory escapes isolated workspace')
        if not command or len(command)!=2 or command[0] not in ('python','python3',sys.executable):raise ValueError('Only original single Python test commands are supported')
        target=(cwd/command[1]).resolve()
        if not target.is_relative_to(cwd/'tests') or target.suffix!='.py' or not target.is_file():raise ValueError('QA command is not an existing isolated Python test')
        paths=[cwd]+[Path(p).resolve() for p in (additional_python_paths or [])]
        if any(not p.is_relative_to(cwd) for p in paths):raise ValueError('QA import path escapes isolated project')
        env=os.environ.copy();env.update(PYTHONPATH=os.pathsep.join(str(p) for p in paths),PYTHONUTF8='1',PYTHONIOENCODING='utf-8')
        argv=[sys.executable,'-X','utf8',str(target)]
        record=dict(index=len(executions),command=argv,working_directory=str(cwd),pythonpath=[str(p) for p in paths],
            test_file=target.relative_to(cwd).as_posix(),test_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),timeout_seconds=10)
        tool('metagpt.qa_command',record)
        process=subprocess.Popen(argv,cwd=cwd,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        record['pid']=process.pid;record['timed_out']=False
        try:stdout,stderr=process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            record['timed_out']=True;process.kill();stdout,stderr=process.communicate()
        outs=stdout.decode('utf-8','replace');errs=stderr.decode('utf-8','replace')
        counts=re.findall(r'Ran (\d+) tests?',outs+'\n'+errs)
        record.update(returncode=process.returncode,stdout=outs,stderr=errs,tests_ran=int(counts[-1]) if counts else None)
        executions.append(record);tool('metagpt.qa_execution',record)
        return outs,errs
    actions.RunCode.run_script=classmethod(run_script)
    return QaEngineer,executions


async def execute(request):
    if not sys.flags.utf8_mode:raise ValueError('Native QA must be launched by run_native_qa.py with UTF8 mode')
    root=Path(request['runtime']).resolve();runtime=load(root)
    QaEngineer,executions=install_qa(runtime,root)
    if request.get('mode')=='probe':
        qa=QaEngineer()
        return dict(event='result',method='metagpt',qa_loaded=True,watch=[x.__name__ for x in qa._rc.watch],
            source_commit=runtime['provenance']['commit'],local_model_inference=False,calls=runtime['calls']())
    package=request['design_message']['structured']['Python package name']
    if Path(package).name!=package or package in ('.','..'):raise ValueError('Unexpected native package name')
    workspace=root/'workspace';workspace.mkdir(exist_ok=True)
    copied={}
    for name,text in request['files'].items():
        target=(workspace/name).resolve()
        if not target.is_relative_to(workspace) or target.exists():raise ValueError('Native continuation must use a new isolated project')
        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(text.encode('utf-8'))
        copied[name]=hashlib.sha256(target.read_bytes()).hexdigest()
    sources=sorted(p for p in (workspace/package/package).glob('*.py') if 'test' not in p.name)
    if not sources:raise ValueError('No real native source files to test')
    qa=QaEngineer();company=runtime['Team']();company.hire([qa]);company.invest(3.0)
    actions=sys.modules['metagpt.actions'];Message=runtime['Message']
    design=request['design_message'];mapping={k:(type(v),...) for k,v in design['structured'].items()}
    model=runtime['ActionOutput'].create_model_class('RestoredNativeDesign',mapping)
    company.environment.publish_message(Message(role=design['role'],content=design['content'],instruct_content=model(**design['structured']),cause_by=actions.WriteDesign))
    from metagpt.utils.special_tokens import FILENAME_CODE_SEP,MSG_SEP
    company.environment.publish_message(Message(role='Engineer',content=MSG_SEP.join(p.name+FILENAME_CODE_SEP+str(p) for p in sources),
        cause_by=actions.WriteCodeReview,sent_from='Engineer',send_to='QaEngineer'))
    await company.run(n_round=request.get('rounds',8))
    messages=[dict(role=m.role,content=m.content,cause_by=getattr(m.cause_by,'__name__',str(m.cause_by)),
        sent_from=str(m.sent_from),send_to=str(m.send_to),structured=m.instruct_content.dict() if m.instruct_content else None)
        for m in company.environment.memory.get()]
    test_root=workspace/package/'tests';tests={p.relative_to(test_root).as_posix():p.read_text(encoding='utf-8') for p in test_root.rglob('*.py')}
    latest={e['test_file']:e for e in executions}
    expected=['tests/test_'+p.name for p in sources]
    final_test_hashes={'tests/'+p.relative_to(test_root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in test_root.rglob('*.py')}
    final_version_executed={name:bool(name in latest and latest[name]['test_sha256']==final_test_hashes.get(name)) for name in expected}
    actual_pass={name:bool(final_version_executed[name] and latest[name]['returncode']==0 and not latest[name]['timed_out'] and latest[name]['tests_ran'] and latest[name]['tests_ran']>0) for name in expected}
    current={name:hashlib.sha256((workspace/name).read_bytes()).hexdigest() for name in copied if name.endswith('.py')}
    unchanged=all(copied[name]==sha for name,sha in current.items())
    unmatched_dev_feedback=[dict(content=m['content'],send_to=m['send_to']) for m in messages if m['cause_by']=='RunCode' and m['send_to']=='Engineer']
    return dict(event='result',method='metagpt',output=dict(test_files=tests,executions=executions,messages=messages),
        checks=dict(original_qa_role_scheduled=qa.test_round>=2,qa_rounds=qa.test_round,expected_test_files=expected,
            generated_test_files=len(tests),execution_attempts=len(executions),latest_actual_pass=actual_pass,final_test_hashes=final_test_hashes,final_version_executed=final_version_executed,
            all_generated_tests_passed=bool(actual_pass) and all(actual_pass.values()),development_source_unchanged=unchanged,
            development_source_hashes=current,unhandled_engineer_feedback=unmatched_dev_feedback),
        author_entry='QaEngineer._observe/_act -> WriteTest -> RunCode.run -> DebugError -> Team/Environment/Role',
        seed_scope='previous real native project after harness-selected original author review; not a fresh startup',
        source_commit=runtime['provenance']['commit'],calls=runtime['calls'](),local_model_inference=False,
        original_complete_benchmark=False,full_autonomous_development_repair_supported=False,
        adaptations=runtime['adaptations']+['UTF8 child Python; Windows process executor replaces RunCode.run_script only',
            'literal_eval for author-created file-info dictionary','QA output paths confined to fresh tests directory','existing reviewed native artifact handoff; no re-generation of upstream stages'])

if __name__=='__main__':
    request=json.loads(sys.stdin.readline())
    with contextlib.redirect_stdout(sys.stderr):result=asyncio.run(execute(request))
    emit(result)
