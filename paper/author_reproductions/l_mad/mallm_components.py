"""Execute pinned MALLM component bodies cited by L-MAD; not LMAD author code.
Original ThresholdConsensus and RankedVoting classes and selected original static
prompt functions are AST-loaded without importing optional torch/sklearn workers.
Only the listed definitions execute. Their bodies are unchanged; full MALLM
coordination/automatic retries/embedding alterations are not run or simulated.
"""
import ast
from abc import ABC,abstractmethod
from dataclasses import dataclass
from enum import Enum
import logging
from pathlib import Path
import sys
from types import ModuleType,SimpleNamespace
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'paper/author_reproductions'))
from author_runtime import source


def load():
    folder,entry=source('mallm')
    module=ModuleType('lmad_selected_mallm_components');sys.modules[module.__name__]=module
    namespace=module.__dict__;namespace.update(ABC=ABC,abstractmethod=abstractmethod,dataclass=dataclass,Enum=Enum,logger=logging.getLogger('mallm'))
    def definitions(relative,names,class_methods=None):
        path=folder/relative;tree=ast.parse(path.read_text(encoding='utf-8-sig'))
        body=[n for n in tree.body if isinstance(n,(ast.ClassDef,ast.FunctionDef)) and n.name in names]
        if class_methods:
            for node in body:
                node.bases=[];node.keywords=[]
                node.body=[n for n in node.body if isinstance(n,ast.FunctionDef) and n.name in class_methods]
        if {n.name for n in body}!=set(names):raise ValueError('Pinned MALLM definition missing')
        unit=ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0),*body],type_ignores=[])
        exec(compile(ast.fix_missing_locations(unit),str(path),'exec'),namespace)
    definitions('mallm/utils/enums.py',['DecisionAlteration'])
    definitions('mallm/utils/types.py',['Agreement','Response','TemplateFilling','VotingResult','VotingResultList','WorkerFunctions'])
    definitions('mallm/decision_protocols/protocol.py',['DecisionProtocol'])
    definitions('mallm/decision_protocols/consensus.py',['ThresholdConsensus','MajorityConsensus','UnanimityConsensus','SupermajorityConsensus','HybridMajorityConsensus'])
    definitions('mallm/decision_protocols/ranked_voting.py',['RankedVoting'])
    definitions('mallm/models/discussion/SimpleResponseGenerator.py',['SimpleResponseGenerator'],['get_filled_template'])
    definitions('mallm/models/discussion/ResponseGenerator.py',['ResponseGenerator'],['extract_agreement','voting_base_prompt','generate_ranking_prompt'])
    return SimpleNamespace(**{n:namespace[n] for n in ['Agreement','TemplateFilling','ThresholdConsensus','HybridMajorityConsensus','RankedVoting','SimpleResponseGenerator','ResponseGenerator','DecisionAlteration']}),entry
