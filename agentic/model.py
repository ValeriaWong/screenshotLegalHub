"""Bounded Responses HTTP reasoning. Secrets stay in process configuration."""
import json
import os
from importlib.resources import files
from urllib.parse import urlsplit
import httpx
from pydantic import Field, SecretStr, model_validator, ValidationError
from .primitives import StrictModel, digest
from .contracts import HarnessError, TransientError, RetryPolicy
from .context import bounded
from .tools import Tool
from .builtin.contracts import ReasoningInput, ReasoningOutput, Reasoning

STAGES = ('planning','facts','assessment','gaps','synthesis')

def stage_prompt(stage):
    if stage not in STAGES:
        raise HarnessError('INVALID_STAGE')
    directory = files('agentic').joinpath('prompts')
    return directory.joinpath('common.md').read_text(encoding='utf-8') + '\n' + directory.joinpath(stage+'.md').read_text(encoding='utf-8')

def strict_schema(model):
    schema = model.model_json_schema()
    def visit(value):
        if isinstance(value, dict):
            value.pop('default', None)
            if value.get('type') == 'object':
                value['additionalProperties'] = False
                value['required'] = list(value.get('properties', {}))
            for item in value.values():
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)
    visit(schema)
    return schema

class ModelConfig(StrictModel):
    url: str
    model: str = Field(min_length=1, max_length=200)
    api_key: SecretStr = Field(exclude=True)
    allow_egress: bool = False
    input_price_per_million: float = Field(ge=0, allow_inf_nan=False)
    output_price_per_million: float = Field(ge=0, allow_inf_nan=False)
    max_output_tokens: int = Field(default=2048, ge=256, le=32768)
    max_input_bytes: int = Field(default=150000, ge=1000, le=1000000)
    timeout_seconds: float = Field(default=45, gt=0, le=120, allow_inf_nan=False)
    format: str = 'json_schema'

    @model_validator(mode='after')
    def validate_endpoint(self):
        url = urlsplit(self.url)
        if (url.scheme != 'https' and not (url.scheme == 'http' and url.hostname in {'127.0.0.1','localhost','::1'})) or not url.hostname:
            raise ValueError('HTTPS required except loopback')
        if url.username or url.password or url.query or url.fragment or not url.path.endswith('/responses'):
            raise ValueError('provide a clean /responses endpoint')
        if self.format not in {'json_schema','json_object'}:
            raise ValueError('unsupported response format')
        if not self.allow_egress or not self.api_key.get_secret_value():
            raise ValueError('explicit egress and credential required')
        return self

    @classmethod
    def from_env(cls):
        names = ['HARNESS_RESPONSES_URL','HARNESS_MODEL','HARNESS_MODEL_API_KEY',
                 'HARNESS_INPUT_PRICE_PER_MILLION','HARNESS_OUTPUT_PRICE_PER_MILLION']
        if any(not os.environ.get(name) for name in names):
            raise HarnessError('MODEL_NOT_CONFIGURED')
        try:
            return cls(url=os.environ[names[0]],model=os.environ[names[1]],api_key=os.environ[names[2]],
                       input_price_per_million=float(os.environ[names[3]]), output_price_per_million=float(os.environ[names[4]]),
                       allow_egress=os.environ.get('HARNESS_ALLOW_MODEL_EGRESS')=='1',
                       format=os.environ.get('HARNESS_MODEL_FORMAT','json_schema'))
        except (ValueError, ValidationError):
            raise HarnessError('INVALID_MODEL_CONFIG') from None

class ResponsesReasoner:
    def __init__(self, config: ModelConfig, *, transport=None):
        self.config, self.transport = config, transport

    @property
    def version(self):
        # Digest contains endpoint/model/cost policy and prompts, never credentials.
        return '0.2.'+digest([self.config.model_dump(mode='json'), [stage_prompt(s) for s in STAGES]])[:16]

    async def execute(self, value, ctx, key):
        cfg = self.config
        prompt = stage_prompt(value.stage)
        payload = bounded({'data':value.payload,'repair_findings':value.repair_findings},ctx._run.request.limits)
        content = json.dumps(payload,ensure_ascii=False,allow_nan=False)
        schema = strict_schema(Reasoning)
        format_spec = ({'type':'json_schema','name':'stage_reasoning','strict':True,'schema':schema}
                       if cfg.format=='json_schema' else {'type':'json_object'})
        body = {'model':cfg.model,'store':False,'instructions':prompt,
                'input':[{'role':'user','content':[{'type':'input_text','text':content}]}],
                'max_output_tokens':cfg.max_output_tokens,'text':{'format':format_spec}}
        if cfg.format=='json_object':
            body['instructions'] += '\nReturn JSON matching this schema: '+json.dumps(schema,ensure_ascii=False)
        # UTF-8 bytes plus framing are conservative reservations, never reported as measured tokens.
        input_bound = len(json.dumps(body,ensure_ascii=False).encode('utf-8')) + 1024
        if input_bound > cfg.max_input_bytes:
            raise HarnessError('CONTEXT_LIMIT')
        cost_bound = (input_bound*cfg.input_price_per_million + cfg.max_output_tokens*cfg.output_price_per_million)/1e6
        reservation = ctx.reserve_model(input_bound+cfg.max_output_tokens,cost_bound)
        ctx._store.save(ctx._run,'model-started',ctx.task_id,stage=value.stage,prompt_digest=digest(prompt),model=cfg.model)
        try:
            async with httpx.AsyncClient(timeout=cfg.timeout_seconds,follow_redirects=False,trust_env=False,transport=self.transport) as client:
                async with client.stream('POST',cfg.url,json=body,headers={'Authorization':'Bearer '+cfg.api_key.get_secret_value()}) as response:
                    if response.status_code==429 or response.status_code>=500:
                        raise TransientError()
                    if response.status_code != 200:
                        raise HarnessError('MODEL_HTTP_ERROR')
                    data = bytearray()
                    async for chunk in response.aiter_bytes():
                        data.extend(chunk)
                        if len(data)>1000000:
                            raise HarnessError('MODEL_RESPONSE_TOO_LARGE')
        except httpx.TimeoutException:
            raise HarnessError('MODEL_TIMEOUT') from None
        except httpx.TransportError:
            raise TransientError() from None
        try:
            raw = json.loads(data)
            usage = raw['usage']
            input_tokens, output_tokens = usage['input_tokens'],usage['output_tokens']
            if (type(input_tokens) is not int or type(output_tokens) is not int or input_tokens<0 or output_tokens<0
                    or input_tokens>input_bound or output_tokens>cfg.max_output_tokens):
                raise HarnessError('INVALID_MODEL_USAGE')
            cost = (input_tokens*cfg.input_price_per_million+output_tokens*cfg.output_price_per_million)/1e6
            reservation.settle(input_tokens+output_tokens,cost)
            if raw.get('status') != 'completed':
                raise HarnessError('MODEL_INCOMPLETE')
            texts = []
            for item in raw.get('output',[]):
                if item.get('type')=='reasoning':
                    continue  # Do not persist internal reasoning.
                if item.get('type')!='message' or item.get('role')!='assistant':
                    raise HarnessError('INVALID_MODEL_RESPONSE')
                for part in item.get('content',[]):
                    if part.get('type')=='refusal':
                        raise HarnessError('MODEL_REFUSED')
                    if part.get('type')!='output_text':
                        raise HarnessError('INVALID_MODEL_RESPONSE')
                    texts.append(part['text'])
            reasoning = Reasoning.model_validate_json(''.join(texts),strict=True)
            bounded(reasoning.model_dump(mode='json'),ctx._run.request.limits)
            result = ReasoningOutput(reasoning=reasoning,provider_response_id=raw['id'],model=cfg.model,
                                     input_tokens=input_tokens,output_tokens=output_tokens,cost=cost)
        except HarnessError:
            raise
        except (KeyError, TypeError, ValueError, AttributeError):
            raise HarnessError('INVALID_MODEL_RESPONSE') from None
        ctx._store.save(ctx._run,'model-completed',ctx.task_id,stage=value.stage,output_digest=digest(reasoning.model_dump(mode='json')))
        return result

    def tool(self):
        return Tool('stage_reasoning',self.version,ReasoningInput,ReasoningOutput,self.execute,
                    permissions=frozenset({'evidence:analyze','model:invoke'}),
                    timeout_seconds=self.config.timeout_seconds+2,
                    retry_policy=RetryPolicy(max_attempts=2,retryable_errors=['TransientError']),
                    description='配置端点上的分阶段 Responses 推理；有预算、来源 Review 与显式失败')
