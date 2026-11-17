from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.v2_cause_batch import OUT,read
from tools.v2_root_review import revise
d=OUT/'zh/zh_0116';c=read(d/'case.json')
c['render_notes']=['转账状态按各自原文显示：1500元已过期，1700元已被接收；不补其他状态。']
revise(d,c,[{'severity':'critical','message_ids':['m012','m014'],
    'problem':'原渲染器只显示金额，遗漏已有原文依据的过期/接收状态，图片无法支持到账判断题。',
    'change':'渲染器显示已过期、已被接收；状态来源分别逐字核验，不为未知状态生成收款成功。'}])
