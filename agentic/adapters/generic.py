"""Transport-neutral public operations and schema discovery."""
from pydantic import Field, ValidationError
from ..primitives import StrictModel
from ..contracts import HarnessError

class RunID(StrictModel):
    run_id: str = Field(min_length=1, max_length=128)

class EventsInput(RunID):
    after: int = Field(default=0, ge=0)

class Empty(StrictModel):
    pass

class GenericAdapter:
    def __init__(self, runtime):
        self.runtime = runtime
        self.operations = {
            'harness_get_run': (RunID, 'Read an owned run'),
            'harness_cancel_run': (RunID, 'Cancel an owned run'),
            'harness_events': (EventsInput, 'Read available ordered events after a cursor'),
            'harness_list_skills': (Empty, 'Discover task abilities'),
            'harness_list_tools': (Empty, 'Discover permitted atomic operations'),
        }
        self.workflow_names = {}
        for name, workflow in runtime.workflows.items():
            public = 'harness_run_' + name
            if len(public) > 64 or not public.replace('_','').isalnum():
                raise HarnessError('INVALID_REGISTRATION', 'workflow name is not function-tool compatible')
            self.workflow_names[public] = name
            self.operations[public] = (workflow.input_model, workflow.description)

    def definitions(self):
        return [dict(name=name, description=description or name, parameters=model.model_json_schema())
                for name,(model,description) in self.operations.items()]

    async def invoke(self, name, arguments, principal, *, idempotency_key=None):
        if name not in self.operations:
            raise HarnessError('UNKNOWN_OPERATION')
        try:
            model, _ = self.operations[name]
            value = model.model_validate(arguments, strict=True)
        except ValidationError:
            raise HarnessError('INVALID_ARGUMENTS') from None
        runtime = self.runtime
        if name in self.workflow_names:
            if not idempotency_key:
                raise HarnessError('IDEMPOTENCY_REQUIRED')
            created = runtime.create_run(dict(workflow=self.workflow_names[name], input=value.model_dump(),
                                              idempotency_key=idempotency_key, limits=runtime.limits.model_dump()), principal)
            return await runtime.wait(created['run_id'], principal)
        if name == 'harness_get_run':
            return runtime.get_run(value.run_id, principal)
        if name == 'harness_cancel_run':
            return await runtime.cancel_run(value.run_id, principal)
        if name == 'harness_events':
            runtime.get_run(value.run_id, principal)
            return [e.model_dump(mode='json') for e in runtime.store.events(value.run_id, value.after)]
        if name == 'harness_list_skills':
            return runtime.list_skills(principal)
        return runtime.list_tools(principal)
