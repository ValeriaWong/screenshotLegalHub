"""Task abilities compose atomic tools through TaskContext."""
import inspect
from dataclasses import dataclass
from typing import Callable
from pydantic import BaseModel
from .contracts import HarnessError

@dataclass(frozen=True)
class Skill:
    name: str
    version: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    handler: Callable
    tools: tuple[str, ...] = ()
    description: str = ''
    constraints: tuple[str, ...] = ()
    lifecycle: str = 'active'
    repair: Callable | None = None
    rules: tuple[Callable, ...] = ()

    def describe(self):
        return dict(name=self.name, version=self.version, description=self.description,
                    input_schema=self.input_model.model_json_schema(), output_schema=self.output_model.model_json_schema(),
                    tools=list(self.tools), constraints=list(self.constraints), lifecycle=self.lifecycle,
                    strategy='repairable' if self.repair else 'execute-once', rules=[r.__name__ for r in self.rules])

class SkillRegistry:
    def __init__(self):
        self._items = {}

    def register(self, skill):
        if (skill.name in self._items or not skill.version or not inspect.iscoroutinefunction(skill.handler)
                or (skill.repair and not inspect.iscoroutinefunction(skill.repair))
                or skill.lifecycle not in {'active', 'deprecated', 'disabled'}):
            raise HarnessError('INVALID_REGISTRATION')
        self._items[skill.name] = skill
        return skill

    def get(self, name):
        if name not in self._items or self._items[name].lifecycle == 'disabled':
            raise HarnessError('UNKNOWN_SKILL')
        return self._items[name]

    def describe(self):
        return [s.describe() for s in self._items.values() if s.lifecycle != 'disabled']
