from screenshotlegal.domain.common.models import digest, now
from screenshotlegal.domain.runtime.models import CasePlan, PlanNode
from screenshotlegal.plugins.skills.registry import CompileError

class CaseCompiler:
    def __init__(self, matters, skills):
        self.matters, self.skills = matters, skills

    def compile(self, case_id, selection, profile, overrides=None):
        pack = self.matters.get(selection['matter_pack_id'], selection['version'])
        manifest = pack['manifest']
        overrides = overrides or {}
        nodes = {}
        def add(capability):
            if capability in nodes:
                return
            skill = self.skills.resolve(capability, manifest['id'], manifest['jurisdiction'], manifest['practice_area'], overrides.get(capability) or profile.get('capabilities', {}).get(capability))
            nodes[capability] = PlanNode(node_id=capability, stage=skill.stage, capability=capability, resolved_skill_id=skill.id, resolved_skill_version=skill.version,
                skill_digest=self.skills.digests[skill.id], depends_on=skill.dependencies, input_selectors=skill.input_schema, output_targets=skill.output_schema)
            for dependency in skill.dependencies:
                add(dependency)
        for cap in [*manifest['required_capabilities'], 'timeline.build', 'matter.route', 'evidence.perceive']:
            add(cap)
        visited, active = set(), set()
        def visit(id):
            if id in active:
                raise CompileError('Dependency cycle')
            if id in visited:
                return
            active.add(id)
            for dep in nodes[id].depends_on:
                if nodes[dep].stage > nodes[id].stage:
                    raise CompileError('Dependency crosses stages backwards')
                visit(dep)
            active.remove(id)
            visited.add(id)
        for id in nodes:
            visit(id)
        payload = dict(case_id=case_id, matter_pack_id=manifest['id'], matter_pack_version=manifest['version'], matter_pack_digest=pack['digest'],
            analysis_profile=profile, analysis_profile_digest=digest(profile), nodes=[n.model_dump() for n in sorted(nodes.values(), key=lambda n:(n.stage,n.node_id))],
            edges=sorted((dep,n.node_id) for n in nodes.values() for dep in n.depends_on))
        return CasePlan(**payload, compiled_at=now(), plan_digest=digest(payload))
