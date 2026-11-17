import pytest
from agentic.primitives import StrictModel
from agentic.contracts import Principal, Plan, TaskSpec
from agentic.core import Runtime
from agentic.planning import Workflow
from agentic.skills import Skill, SkillRegistry
from agentic.tools import ToolRegistry
from agentic.state import SQLiteStore

class Number(StrictModel):
    value: int

async def increment(value, ctx):
    return {'value':value.value+1}

@pytest.fixture
def principal():
    return Principal(subject='alice', permissions=frozenset({'run:create','run:read','run:cancel','run:resume','run:review','compute'}))

@pytest.fixture
async def factory():
    runtimes = []
    def make(handler=increment, *, repair=None, rules=(), plan=None, tools=None, store=None, limits=None, human=False):
        registry = SkillRegistry()
        registry.register(Skill('step','1',Number,Number,handler, tools=tuple(t['name'] for t in tools.describe()) if tools else (),
                                repair=repair,rules=rules))
        def default_plan(value):
            return Plan(tasks=[TaskSpec(task_id='first',stage_id=0,skill='step',input=value.model_dump(),human_review=human)])
        runtime = Runtime(tools or ToolRegistry(), registry, [Workflow('work','1',Number,plan or default_plan)], store or SQLiteStore(),limits=limits)
        runtimes.append(runtime)
        return runtime
    yield make
    for runtime in runtimes:
        if not runtime.closed:
            await runtime.close()

def request(key='r1', **extra):
    return dict(workflow='work',input={'value':2},idempotency_key=key,**extra)
