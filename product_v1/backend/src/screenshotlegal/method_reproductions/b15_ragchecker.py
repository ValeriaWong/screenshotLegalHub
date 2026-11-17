"""RAGChecker (Ru et al., arXiv:2408.08067), author API evaluator integration.
Paper: https://arxiv.org/abs/2408.08067
Author: https://github.com/amazon-science/RAGChecker @ 6091f08c00e676e87a970f2aeb4a23a484746348
Original I/O: query + ground-truth answer + generated response + retrieved passages
-> claim triplets / entailment matrices / original 11 metrics. This is an evaluator,
not a CaseAnalysisOutput-generating agent; it is intentionally outside METHOD_MODULES.
Original benchmark: 4k questions in 10 domains plus human meta-evaluation.
Fidelity and exact source versions: paper/author_reproductions/ragchecker/product_adapter.py.
Product adaptation: free-text VQA with reference uses original all metrics; categorical
VQA checks only original evidence text faithfulness against actual frozen KIE input.
KIE needs a frozen human transcript, uses original overall metrics, excludes geometry.
No local weights; DeepSeek judge replacement and predicted-context limitations recorded.
No claim of pixel OCR accuracy, legal correctness or original paper benchmark scores.
The caller must supply a durable, explicitly budgeted raw_call; no hidden API client.
"""
import os
from pathlib import Path
from .author_bridge import REPO,stream_author
METHOD_NAME='b15_ragchecker'
PAPER_ID='B15'

async def evaluate(rag_results,raw_call,author_record=None,metrics=None):
    python=REPO/'paper/.author_envs/ragchecker'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    if not python.is_file():raise ValueError('RAGChecker 独立环境未配置：paper/author_reproductions/ragchecker/README.md')
    async def handle(event):
        if event['event']=='tool':
            if author_record:await author_record(event['action'],event['result'])
            return dict(ok=True)
        return await raw_call(event['stage'],event['messages'],event['original_parameters'])
    return await stream_author(python,REPO/'paper/author_reproductions/ragchecker/product_adapter.py',
        dict(rag_results=rag_results,metrics=metrics or ['all_metrics']),handle,python_utf8=True)
