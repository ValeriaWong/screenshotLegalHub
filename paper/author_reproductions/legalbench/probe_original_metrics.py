"""Independent arithmetic probes of unchanged LegalBench evaluator caveats, zero API."""
import importlib.util,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE.parent))
from author_runtime import source
folder,pin=source('legalbench');spec=importlib.util.spec_from_file_location('author_eval',folder/'evaluation.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
rows=[dict(name='numeric_decimal_representation',prediction='$100.00',reference='$100',expected_equal_numeric_value_score=1.,original_score=float(m.evaluate('sara_numeric',['$100.00'],['$100'])),reason='Original removes decimal points before selecting the first integer.'),
      dict(name='ssla_perfect_two_item_set',prediction='Alpha,Beta',reference='Alpha,Beta',expected_set_f1=1.,original_score=float(m.evaluate_ssla(['Alpha,Beta'],['Alpha,Beta'])),reason='Original adds remaining false positives inside each reference-item iteration.'),
      dict(name='successor_dispatch_shadowing',prediction='express agreement',reference='express agreement,de facto merger',expected_set_f1=2/3,original_dispatch_score=float(m.evaluate('successor_liability',['express agreement'],['express agreement,de facto merger'])),original_direct_set_f1=float(m.evaluate_successor_liability(['express agreement'],['express agreement,de facto merger'])),reason='Task is in EXACT_MATCH_BALANCED_ACC_TASKS; evaluate() reaches that branch before its specialized F1 branch.')]
out=dict(source_commit=pin['commit'],model_requests=0,source_changed=False,scope='Source behavior vs independent arithmetic/protocol expectations; not legal accuracy',probes=rows)
(HERE/'source_metric_probe.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(out,ensure_ascii=False))
