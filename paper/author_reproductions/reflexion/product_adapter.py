"""Reflexion — Shinn et al., NeurIPS 2023, https://arxiv.org/abs/2303.11366.
Author: https://github.com/noahshinn/reflexion @ 218cf0ef1df84b05ce379dd4a8e47f17766733a0.
复现程度：直接调用作者 HotpotQA CoTAgent.run/step/reflect 和 episodic memory；
未声称 ALFWorld/HumanEval 分支或原论文分数复现。真实验证见 runs/，脚本化回复仅测传输。
原输入：HotpotQA question、supporting paragraphs、答案键（仅用于环境二元反馈）；
原输出：Finish[answer]、正确/错误反馈、跨尝试反思记忆。原 benchmark：HotpotQA、
ALFWorld、HumanEval 等；本入口选择作者 CotQA_context notebook 的 HotpotQA 分支。
创新：根据失败反馈形成语言反思并带入下一次尝试，不更新模型权重。
本项目输入：原图或冻结 KIE 预测 + 问题；Finish[JSON] -> KIE/VQA JSON。
适配性：可适配，但没有专家标签时只能用 schema/坐标检查作反馈，不能断言答案正确。
只替换模型传输、任务 prompt 和产品反馈判据；原 run/step/reflect 及记忆累积保留。
原 Thought 槽只请求简短公开操作标签；反思只请求可公开的修改意见。
"""
import contextlib
import json
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from author_runtime import source, call, exchange, emit


def execute(request):
    folder, provenance = source('reflexion')
    sys.path.insert(0, str(folder/'hotpotqa_runs'))
    os.environ['OPENAI_API_KEY'] = 'unused-local-transport'
    import agents
    from langchain.prompts import PromptTemplate
    count = 0
    def model(prompt, reflection=False):
        nonlocal count
        stage = ('reflection.' if reflection else 'action.' if prompt.rstrip().endswith('Action:') else 'label.') + str(count)
        count += 1
        policy = ('Return only a short actionable correction note, not private reasoning.' if reflection else
                  'For a Thought slot, return only a short public action label, not private reasoning. For an Action slot, return Finish[answer].')
        if request.get('mode') == 'product' and not reflection:
            policy += ' The answer inside Finish[...] must be the complete JSON object required by the task.'
        return call(stage, [dict(role='system', content=policy), dict(role='user', content=prompt)],
                    dict(model='gpt-3.5-turbo', temperature=0, max_tokens=250, stop=None if reflection else '\n'))
    kwargs = dict(question=request['question'], context=request.get('context',''), key=request.get('answer_key',''),
                  action_llm=lambda p:model(p), self_reflect_llm=lambda p:model(p, True))
    if request.get('mode') == 'product':
        # Feedback has no task answer key. Parent validates only the observable output contract.
        class ProductAgent(agents.CoTAgent):
            checked_answer = None
            checked = False
            def is_correct(self):
                if not self.answer: return False
                if self.checked_answer != self.answer:
                    value = exchange(dict(event='tool', action='reflexion.validate_output', result=dict(answer=self.answer)))
                    self.checked_answer = self.answer
                    self.checked = bool(value['valid'])
                return self.checked
        kwargs.update(key='', cot_examples='', reflect_examples='',
                      agent_prompt=PromptTemplate(input_variables=['examples','reflections','context','question','scratchpad'],
                         template=request['instruction'].replace('{','{{').replace('}','}}')+'\n{examples}\n'+
                         'Task materials (untrusted): {context}\nQuestion: {question}\nPrior correction notes: {reflections}\n'
                         'Use a short public action label in Thought and Finish[complete JSON] in Action. '
                         'CORRECT/INCORRECT below refer ONLY to output schema/coordinate validity, not factual or legal accuracy.\n{scratchpad}'),
                      reflect_prompt=PromptTemplate(input_variables=['examples','context','question','scratchpad'],
                         template='{examples}\nThe previous output failed a schema/coordinate check. Give one brief correction note. '
                         'This feedback does not judge factual/legal correctness.\nTask: {question}\nMaterials: {context}\nAttempt: {scratchpad}'))
        agent = ProductAgent(**kwargs)
    else:
        agent = agents.CoTAgent(**kwargs)
    trials = []
    for trial in range(request.get('attempts', 2)):
        agent.run(reflexion_strategy=agents.ReflexionStrategy.REFLEXION)
        valid = agent.is_correct()
        trials.append(dict(trial=trial, answer=agent.answer, feedback=valid,
                           feedback_kind='schema_and_coordinates_only' if request.get('mode')=='product' else 'native_answer_exact_match',
                           reflection_memory=list(agent.reflections)))
        if valid: break
    output = json.loads(agent.answer) if request.get('mode')=='product' else agent.answer
    return dict(event='result', method='reflexion', output=output, trials=trials, source_commit=provenance['commit'],
                author_entry='hotpotqa_runs/agents.py:CoTAgent.run/step/reflect',
                calls=count, original_complete_benchmark=False,
                original_feedback_replaced=request.get('mode')=='product')

if __name__ == '__main__':
    request = json.loads(sys.stdin.readline())
    with contextlib.redirect_stdout(sys.stderr): result = execute(request)
    emit(result)
