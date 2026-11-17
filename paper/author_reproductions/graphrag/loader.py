"""Load fixed author core; bypass only unused eager vector-backend registration.
GraphRAG v0.1.1 vector_stores.__init__ eagerly imports LanceDB/Azure Search even
for global query. No selected global/index workflow calls these backends. Their
backend constructors are unavailable; original base.py types and the two factory
classes load unchanged (deferred annotations avoid importing unused backends).
No algorithms, scores, graph clusters or model outputs are implemented here.
"""
import ast,importlib,json,os,sys,types
from enum import Enum
from typing import ClassVar
from pathlib import Path
HERE=Path(__file__).parent;ROOT=HERE.parents[2]
def load():
    sys.path[:0]=[str(HERE.parent),str(ROOT/'paper/upstream_sources/graphrag')]
    from author_runtime import source
    folder,identity=source('graphrag')
    os.environ['TIKTOKEN_CACHE_DIR']=str(ROOT/'paper/.cache/tiktoken')
    name='graphrag.vector_stores'
    package=types.ModuleType(name);package.__path__=[str(folder/'graphrag/vector_stores')];package.__package__=name
    sys.modules[name]=package
    base=importlib.import_module(name+'.base')
    for item in ['BaseVectorStore','VectorStoreDocument','VectorStoreSearchResult']:setattr(package,item,getattr(base,item))
    typing_name=name+'.typing'
    factory=types.ModuleType(typing_name);factory.__file__=str(folder/'graphrag/vector_stores/typing.py')
    factory.Enum=Enum;factory.ClassVar=ClassVar
    tree=ast.parse(Path(factory.__file__).read_text(encoding='utf-8'))
    body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0)]+[n for n in tree.body if isinstance(n,ast.ClassDef)]
    exec(compile(ast.fix_missing_locations(ast.Module(body=body,type_ignores=[])),factory.__file__,'exec'),factory.__dict__)
    sys.modules[typing_name]=factory
    package.VectorStoreFactory=factory.VectorStoreFactory;package.VectorStoreType=factory.VectorStoreType
    return folder,identity
