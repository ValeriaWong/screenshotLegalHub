"""Deterministic schema validation runs before optional rule/LLM reviewers."""
import inspect
from pydantic import ValidationError, BaseModel
from .contracts import ReviewResult

async def review(skill, output, context):
    try:
        raw = output.model_dump(mode='json') if isinstance(output, BaseModel) else output
        value = skill.output_model.model_validate(raw, strict=True).model_dump(mode='json')
    except ValidationError:
        return None, ReviewResult(status='REWORK', score=0, reviewer_type='schema',
                                  findings=['output does not match declared schema'], suggested_actions=['repair output schema'])
    score, findings, actions = 1.0, [], []
    for rule in skill.rules:
        result = rule(value, context)
        if inspect.isawaitable(result):
            result = await result
        result = ReviewResult.model_validate(result)
        if result.status != 'PASS':
            return value, result
        score = min(score, result.score)
        findings.extend(result.findings); actions.extend(result.suggested_actions)
    return value, ReviewResult(status='PASS', score=score, findings=findings, suggested_actions=actions,
                               reviewer_type='rule' if skill.rules else 'schema')
