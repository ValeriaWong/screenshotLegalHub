import hashlib
import yaml
from screenshotlegal.domain.legal.models import SkillManifest

class CompileError(ValueError):
    pass

class SkillRegistry:
    def __init__(self, directory, settings):
        self.settings = settings
        self.skills = {}
        self.digests = {}
        for path in sorted(directory.glob('*.yaml')):
            skill = SkillManifest.model_validate(yaml.safe_load(path.read_text(encoding='utf-8')))
            if skill.id in self.skills:
                raise CompileError('Duplicate skill ID')
            self.skills[skill.id] = skill
            implementation = (directory.parents[0] / 'deterministic.py').read_bytes()
            self.digests[skill.id] = hashlib.sha256(path.read_bytes() + implementation).hexdigest()

    def authorize(self, skill):
        trust = skill.trust.get('level', 'external_untrusted')
        if trust not in {'builtin','trusted'} or (trust != 'builtin' and skill.id not in self.settings.skill_allowlist):
            raise PermissionError('Skill is not allowlisted and trusted')
        required = {'network','filesystem_read','filesystem_write','model','retrieval','authority_search'}
        if not required <= skill.permissions.keys():
            raise PermissionError('Missing permission declarations')
        for permission, enabled in skill.permissions.items():
            if enabled and permission not in self.settings.allowed_permissions:
                raise PermissionError(f'Permission denied: {permission}')

    def resolve(self, capability, matter, jurisdiction, practice_area, override=None):
        candidates = []
        for skill in self.skills.values():
            if skill.capability != capability:
                continue
            applies = skill.applies_to
            if not all('*' in applies.get(key, ['*']) or value in applies.get(key, []) for key,value in [('matters',matter),('jurisdictions',jurisdiction),('practice_areas',practice_area)]):
                continue
            rank = 2 if matter in applies.get('matters', []) else 3 if jurisdiction in applies.get('jurisdictions', []) or practice_area in applies.get('practice_areas', []) else 4
            candidates.append((rank, skill))
        if override:
            candidates = [(1, s) for _,s in candidates if s.id == override]
        if not candidates:
            raise CompileError(f'Missing capability: {capability}')
        best = min(rank for rank,_ in candidates)
        winners = [s for rank,s in candidates if rank == best]
        if len(winners) != 1:
            raise CompileError(f'Ambiguous capability: {capability}')
        self.authorize(winners[0])
        return winners[0]
