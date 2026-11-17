"""Runnable Tool/Skill extension; uses the package-owned canonical JSON digest."""
import asyncio
from pydantic import Field
from ..primitives import StrictModel, digest
from ..contracts import Plan, TaskSpec, Principal
from ..tools import Tool, ToolRegistry
from ..skills import Skill, SkillRegistry
from ..planning import Workflow
from ..core import Runtime
from ..state import SQLiteStore

class Text(StrictModel):
    text: str = Field(max_length=10000)

class Fingerprint(StrictModel):
    sha256: str = Field(pattern=r'^[0-9a-f]{64}$')

def fingerprint(value, context, operation_key):
    return {'sha256':digest(value.text)}

async def describe(value, context):
    return (await context.call_tool('fingerprint', value.model_dump())).data

def plan(value):
    return Plan(tasks=[TaskSpec(task_id='digest',stage_id=0,skill='describe',input=value.model_dump())])

async def main():
    tools,skills=ToolRegistry(),SkillRegistry()
    tools.register(Tool('fingerprint','1',Text,Fingerprint,fingerprint,permissions=frozenset({'compute'})))
    skills.register(Skill('describe','1',Text,Fingerprint,describe,tools=('fingerprint',)))
    runtime=Runtime(tools,skills,[Workflow('fingerprint','1',Text,plan)],SQLiteStore())
    principal=Principal(subject='local',permissions=frozenset({'run:create','run:read','compute'}))
    try:
        run=runtime.create_run({'workflow':'fingerprint','input':{'text':'reusable extension'},'idempotency_key':'extension-demo'},principal)
        result=await runtime.wait(run['run_id'],principal)
        assert result['status']=='COMPLETED'
        print(result['result'])
    finally: await runtime.close()

if __name__=='__main__': asyncio.run(main())
