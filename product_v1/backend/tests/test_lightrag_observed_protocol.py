"""Regression for supplier output observed in the real Chinese KIE-to-graph run."""
import ast,importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
def test_normalizes_only_tuple_boundaries_and_keeps_quoted_evidence():
    path=ROOT/'paper/author_reproductions/lightrag/product_adapter.py'
    tree=ast.parse(path.read_text(encoding='utf-8'))
    definition=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='canonical_tuple_terminators')
    scope={};exec(compile(ast.Module(body=[definition],type_ignores=[]),str(path),'exec'),scope)
    normalize=scope['canonical_tuple_terminators']
    raw='("entity"<|>"微信"<|>"organization"<|>"原文含）##字符串")##\n("entity"<|>"淘宝"<|>"organization"<|>"平台"）##<|COMPLETE|>'
    expected=raw.replace('"平台"）##','"平台")##')
    assert normalize(raw)==expected
    assert normalize(expected)==expected
