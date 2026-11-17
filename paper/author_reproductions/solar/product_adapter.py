"""SOLAR — Sadowski & Chudziak, CIKM 2025, https://arxiv.org/abs/2509.00710.
Author https://github.com/albsadowski/solar @ 067f8f78b128dc7647c8a54b2560a612fae91a87.
复现程度：作者 Stage II 的 StateGraph、ABox 归一化、NLTK 验证与固定税法解释器
直接执行；使用作者提供的 sara_tbox_o1.json 与 sara_interpreter_o1.py。
Stage I 法条→TBox/解释器生成尚未真实验证；此入口不执行任意模型生成的 Python。
原输入：SARA numeric 的 description 和 question，以及税法 TBox / interpreter；
原输出：数值 answer 与 ABox。示例：给定应税收入/申报身份，计算指定税年的税额。
创新：知识获取与知识应用两阶段、显式 TBox/ABox、符号规则和可执行解释器。
适配边界：现有中国聊天截图的消息 KIE、通用全局 VQA 不等同美国税法计算，
不能直接复用此 TBox 认定中国民事责任。本文件提供原任务验证和显式规则域入口；
没有经审查的对应规则包时，不将其冒充 KIE/VQA 方法。用户暂缓专家金标与此无关。
模型结构化输出经 schema 校验后交回原图；传输可替换 DeepSeek，必须记录实际模型。
"""
import contextlib
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from author_runtime import source, call, emit


def execute(request):
    folder, provenance = source('solar')
    sys.path.insert(0, str(folder))
    from solar.model import TBox
    from solar.knowledge_application import predict
    if request.get('mode') not in ['native', 'sara_rule_domain']:
        raise ValueError('SOLAR SARA rule pack is not a Chinese screenshot KIE/global-VQA rule pack')
    stages = []
    class Broker:
        def with_structured_output(self, schema):
            class Structured:
                def invoke(self, prompt):
                    stage = 'extract_abox' if schema.__name__ == 'FactExtractionResult' else 'identify_taxpayer'
                    raw = call(stage, [dict(role='system', content='Return only a JSON object matching this schema. Explanations must be brief public factual justifications.\n'+json.dumps(schema.model_json_schema(), ensure_ascii=False)),
                                       dict(role='user', content=prompt)], dict(original_interface='with_structured_output', schema=schema.__name__))
                    parsed = schema.model_validate_json(raw)
                    stages.append(dict(stage=stage, output=parsed.model_dump(mode='json')))
                    return parsed
            return Structured()
    tbox = TBox.model_validate_json((folder/'eval/sara_tbox_o1.json').read_text(encoding='utf-8'))
    interpreter = (folder/'eval/sara_interpreter_o1.py').read_text(encoding='utf-8')
    answer, abox = predict(Broker(), request['description'], request['question'], tbox, interpreter, False)
    return dict(event='result', output=dict(answer=answer, abox=abox), stages=stages,
                source_commit=provenance['commit'], original_complete_benchmark=False,
                author_entry='solar/knowledge_application.py:predict -> graph',
                rule_domain='SARA historical US tax statutes; not current legal advice',
                stage_i_generated_here=False)

if __name__ == '__main__':
    request = json.loads(sys.stdin.readline())
    with contextlib.redirect_stdout(sys.stderr): result = execute(request)
    emit(result)
