"""Run with python -I verify_wheel.py <installed-target> <wheel> <source-root>."""
import asyncio
import importlib.abc
import json
from pathlib import Path
import sys
import tempfile
import zipfile

installed,wheel,source=map(Path,sys.argv[1:])
sys.path.insert(0,str(installed.resolve()))
class BlockApplications(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path=None,target=None):
        if fullname.split('.')[0] in {'screenshotlegal','legalhub'}:
            raise AssertionError('Imported old application: '+fullname)
sys.meta_path.insert(0,BlockApplications())
import agentic
from agentic.examples.report import example
assert installed.resolve() in Path(agentic.__file__).resolve().parents
with zipfile.ZipFile(wheel) as archive:
    members=archive.namelist()
    assert 'agentic/adapters/product.py' not in members
    assert 'agentic/examples/retrieval.py' not in members
    for name in ['builtin/tools.py','builtin/workflow.py','model.py','report.py','templates/report.html',
                 'templates/report.js','templates/report.css','examples/case.json','examples/model.env.example',
                 'examples/harness-manifest.json',*['prompts/'+s+'.md' for s in ['common','planning','facts','assessment','gaps','synthesis']]]:
        assert 'agentic/'+name in members,name
    checked=0
    for member in members:
        if member.startswith('agentic/') and not member.endswith('/'):
            local=source/member
            assert local.is_file(),member
            assert archive.read(member)==local.read_bytes(),member
            checked+=1
    metadata=archive.read('screenshotlegal_agentic-0.2.0.dist-info/METADATA').decode()
    requires=[line for line in metadata.splitlines() if line.startswith('Requires-Dist:')]
    assert len(requires)==4 and not any('screenshotlegal' in line or 'legalhub' in line for line in requires)
with tempfile.TemporaryDirectory() as directory:
    result,html=asyncio.run(example(directory))
assert result['result']['status']=='COMPLETED'
assert result['result']['usage']['tool_calls']==5
assert len(result['result']['tasks'])==5 and '模型未调用' in html
assert not any(name.split('.')[0] in {'screenshotlegal','legalhub'} for name in sys.modules)
print(json.dumps({'status':'PASS','version':agentic.__version__,'verified_package_files':checked,
                  'stages':5,'tool_calls':5,'model_calls':0,'old_application_imports':'blocked','dependencies':requires}))
