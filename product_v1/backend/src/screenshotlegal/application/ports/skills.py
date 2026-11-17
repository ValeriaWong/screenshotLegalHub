from typing import Protocol
from screenshotlegal.domain.legal.models import SkillManifest
from screenshotlegal.domain.common.models import SkillContext, SkillInput, SkillResult

class LegalSkill(Protocol):
    manifest: SkillManifest
    async def run(self, context: SkillContext, input: SkillInput) -> SkillResult: ...
