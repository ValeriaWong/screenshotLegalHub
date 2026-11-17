import { describe, it, expect } from 'vitest';
import { flowDecision, failureGuide } from './presentation';
describe('explain outcomes without implying quality approval',()=>{
 it('does not turn successful responses into an approval',()=>{const result=flowDecision('awaiting_human_review',{qa_success:26,qa_requests:26,formal_releases:0});expect(result.title).toBe('这轮还需要人工审核');expect(result.meaning).toContain('不代表答案正确');expect(result.next).toContain('人工审核结论')});
 it('does not claim a release when no release result is recorded',()=>{expect(flowDecision('completed',{}).meaning).toContain('未说明审核或发布已完成')});
 it('explains the cost consequence before retrying an unknown outcome',()=>{expect(failureGuide('unknown_outcome')[1]).toContain('再次计费')});
});
