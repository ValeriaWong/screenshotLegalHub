"""Preserve explicit reasoning choices and freeze the supplier parameters actually used."""
from screenshotlegal.research.gateway import author_inference_parameters

def test_verified_aiping_deepseek_author_defaults_disable_thinking_without_mutating_snapshot():
    model=dict(endpoint='https://www.aiping.cn/v1',model='DeepSeek-V4.1-Flash-1017',parameters=dict(temperature=0,max_tokens=100))
    result=author_inference_parameters(model)
    assert result==dict(temperature=0,max_tokens=100,enable_thinking=False,thinking=dict(type='disabled'))
    assert model['parameters']==dict(temperature=0,max_tokens=100)

def test_explicit_thinking_setting_is_retained_and_other_providers_are_unchanged():
    for flag in [True,False]:
        m=dict(endpoint='https://aiping.cn/v1',model='deepseek-v4.1-flash',parameters=dict(enable_thinking=flag))
        assert author_inference_parameters(m)==dict(enable_thinking=flag,thinking=dict(type='enabled' if flag else 'disabled'))
    for endpoint,model in [('https://aiping.cn.attacker.example/v1','DeepSeek'),('https://other.example/v1','DeepSeek'),('https://aiping.cn/v1','OtherModel')]:
        assert author_inference_parameters(dict(endpoint=endpoint,model=model,parameters=dict(temperature=.7)))==dict(temperature=.7)
