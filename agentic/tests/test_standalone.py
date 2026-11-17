import ast
from pathlib import Path
import subprocess
import sys

def test_runtime_has_no_old_application_imports():
    root=Path(__file__).parents[1]
    for file in list(root.glob('*.py')) + list((root/'builtin').glob('*.py')) + list((root/'adapters').glob('*.py')) + list((root/'examples').glob('*.py')):
        tree=ast.parse(file.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            names=([node.module or ''] if isinstance(node,ast.ImportFrom) else [a.name for a in node.names] if isinstance(node,ast.Import) else [])
            assert not any(n.split('.')[0] in {'screenshotlegal','legalhub'} for n in names), str(file)

def test_e2e_with_old_application_imports_blocked(tmp_path):
    root=Path(__file__).parents[2]
    code = '''
import sys, importlib.abc, asyncio, tempfile
sys.path.insert(0,sys.argv[1])
class BlockOld(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path=None,target=None):
        if fullname.split('.')[0] in {'screenshotlegal','legalhub'}:
            raise RuntimeError('Old application imported: '+fullname)
sys.meta_path.insert(0,BlockOld())
from agentic.examples.report import example
with tempfile.TemporaryDirectory() as directory:
    run,html=asyncio.run(example(directory))
assert run['result']['status']=='COMPLETED'
assert '<!doctype html>' in html
assert not any(x.split('.')[0] in {'screenshotlegal','legalhub'} for x in sys.modules)
print('STANDALONE_PASS')
'''
    result=subprocess.run([sys.executable,'-I','-c',code,str(root)],cwd=tmp_path,capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
    assert 'STANDALONE_PASS' in result.stdout
