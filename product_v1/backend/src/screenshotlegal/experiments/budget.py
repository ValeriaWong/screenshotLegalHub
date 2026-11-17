import time
from screenshotlegal.research.contracts import dumps
from screenshotlegal.research.gateway import ModelFailure

class BudgetExceeded(ModelFailure):
    def __init__(self,message): super().__init__('budget_exhausted',message,False)
class BudgetTracker:
    def __init__(self,limits,usage=None):
        self.limits=limits;self.start=time.monotonic()
        self.usage=dict(model_calls=0,tool_calls=0,input_tokens=0,output_tokens=0,reserved_input_tokens=0,
                        missing_usage_calls=0,cost=None,cost_recorded=0,elapsed_ms=0)
        self.usage.update(usage or {})
    def remaining_seconds(self):
        remaining=self.limits['max_wall_time_s']-self.usage.get('elapsed_ms',0)/1000-(time.monotonic()-self.start)
        if remaining<=0: raise BudgetExceeded('实验已达到总时长上限')
        return remaining
    def reserve(self,messages):
        self.remaining_seconds()
        if self.usage['model_calls']>=self.limits['max_model_calls']: raise BudgetExceeded('模型调用次数已用完')
        # Explicit conservative reservation, not a claim about a vendor's tokenizer.
        bound=len(dumps(messages).encode('utf-8'))+512+64*len(messages)
        spent=self.usage['input_tokens']+self.usage['reserved_input_tokens']
        if spent+bound>self.limits['max_input_tokens']: raise BudgetExceeded('当前输入超出剩余 token 保守预留预算')
        cap=min(self.limits['max_output_per_call'],self.limits['max_output_tokens']-self.usage['output_tokens'])
        if cap<1: raise BudgetExceeded('输出 token 预算已用完')
        self.usage['model_calls']+=1;self.usage['reserved_input_tokens']+=bound
        return cap
    def charge(self,response):
        usage=response.get('usage')
        good=isinstance(usage,dict) and all(type(usage.get(k)) is int and usage[k]>=0 for k in ['prompt_tokens','completion_tokens'])
        if good:
            self.usage['input_tokens']+=usage['prompt_tokens'];self.usage['output_tokens']+=usage['completion_tokens']
            self.usage['reserved_input_tokens']=0
        else:self.usage['missing_usage_calls']+=1
        cost=response.get('cost_estimate')
        if isinstance(cost,(int,float)) and cost>=0:
            self.usage['cost']=(self.usage['cost'] or 0)+cost;self.usage['cost_recorded']+=1
        return good
    def check_actual(self):
        if self.usage['input_tokens']>self.limits['max_input_tokens'] or self.usage['output_tokens']>self.limits['max_output_tokens']:
            raise BudgetExceeded('供应商报告用量超过预算，已停止后续调用；本次不纳入等预算比较')
    def tool(self):
        self.remaining_seconds()
        if self.usage['tool_calls']>=self.limits['max_tool_calls']:raise BudgetExceeded('工具调用次数已用完')
        self.usage['tool_calls']+=1
    def snapshot(self):
        return dict(self.usage,elapsed_ms=self.usage['elapsed_ms']+round((time.monotonic()-self.start)*1000))
