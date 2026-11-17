import { api } from "../../api/client";
export { api };
export const key = () => crypto.randomUUID();
export interface Message { id: string; speaker: string; text: string; timestamp: string | null; source_refs: Record<string, unknown>[] }
export interface Question { id: string; question: string; task_type: string; answer: string | null; gold: boolean; message_ids: string[] }
export interface Content {
  title: string; category: string; language: string; platform: string; kind: "synthetic" | "original";
  source_text: string; source_refs: Record<string, unknown>[]; messages: Message[]; questions: Question[];
  tags: string[]; original_assets: { id: string; sha256: string; mime_type: string; origin?: string }[];
  metadata: Record<string, unknown>; visual_role?: string; original_layout?: PageLayout[];
}
export interface Region { message_id: string; bbox: number[] }
export interface PageLayout { page: number; width: number; height: number; boxes: Region[] }
export interface ReviewComment { applicability?: "revision" | "source"; state?: string; state_event_id?: string | null; processing?: { reason: string; candidate_sample_id?: string; candidate_revision?: number }; id: string; sample_id: string; revision: number; message_id: string | null; body: string; use_for_generation: boolean; created_at: string; editor: string; quality_id: string; message_snapshot?: Message; supersedes?: string | null }
export interface Render { width: number; page_height: number; font_size: number }
export const defaultRender: Render = { width: 760, page_height: 1100, font_size: 24 };
export interface Sample { language?: string; platform?: string; id: string; dataset: string; revision: number; title: string; category: string; tags: string[]; status: string; batch_id: string | null; prompt_id: string | null; published_manifest: string | null; render_job_id: string }
export interface Revision { renderer_version?: string; id: string; sample_id: string; number: number; content: Content; content_hash: string; note: string; diff: Record<string, unknown>; created_at: string; editor: string; render: Render; layout?: PageLayout[] }
export interface Quality { reviewed_object?: { visual_role: string; expected_pages: number }; input_scope_status?: string; input_contract_version?: string; binding_status?: string; review_scope?: string; coverage?: string; protocol_id?: string; binding?: Binding | null; id: string; sample_id: string; revision: number; method: string; verdict: string; score: number | null; dimensions: Record<string, number>; findings: string; suggestions: string; process: string; editor: string; created_at: string; supersedes: string | null; prompt_id?: string; response?: Record<string, unknown> }
export interface Job { id: string; kind: string; status: string; phase: string; created_at: string; updated_at: string; checkpoints: Record<string, unknown>; payload: Record<string, any>; error: { category: string; message: string; retryable: boolean } | null; parent_job_id?: string; cancel_requested: boolean }
export interface Prompt { id: string; purpose: string; name: string; version: number; markdown: string; note: string; feedback_ids: string[]; sha256: string; parent_id: string | null; created_at: string }
export interface Binding { sha256: string; sample_id: string; revision: number; manifest_id: string; manifest_hash: string; asset_hashes: string[]; visual_role: string; content_hash: string }
export interface Detail { generation_feedback?: ReviewComment[]; binding?: Binding | null; gold_certifications?: Record<string, unknown>[]; comment_events?: Record<string, unknown>[]; sample: Sample; revision: Revision; revisions: Revision[]; quality: Quality[]; comments: ReviewComment[]; jobs: Job[] }
export interface Draft { id: string; sample_id: string; base_revision: number; expected_version: number; draft_id: string; version: number; content: { content: Content; note: string; render: Render; layout?: PageLayout[]; layout_manifest_id?: string | null; coordinates_unlocked?: boolean; comment_drafts?: Record<string, string>; text_dirty?: boolean }; updated_at: string }
export interface Manifest { visual_role?: string; validation?: { valid: boolean; unannotated?: boolean }; id: string; revision: number; text_hash: string; pages: { page: number; width: number; height: number; sha256: string; boxes: { message_id: string; bbox: number[] }[] }[] }
export interface Release { contract?: string; id: string; name: string; sha256: string; created_at: string; entries: { sample_id: string; batch_id: string | null; revision: Revision; manifest: Manifest; binding?: Binding; quality_id?: string }[] }
export interface Batch { id: string; name: string; status: string; model: { name: string }; source: Revision; prompt: Prompt; count: number; sample_ids: string[]; job_id: string; package_ready: boolean; render_statuses: string[]; error?: { message: string } }
export interface Comparison { quality_attempts?: number; failed_attempts?: number; unknown_attempts?: number; stage: string; protocol_id: string; protocol?: Record<string, unknown>; coverage?: number; cohort_total?: number; sample_set_hash?: string; comparison_note?: string; batch_id: string; prompt_id: string; samples: number; reviewed_samples: number; human_mean: number | null; model_mean: number | null; human_scored: number; model_scored: number; human_pass_rate: number | null; corrections: number; quality_ids: string[] }
export interface EvalRun { id: string; name: string; status: string; release_id: string; mode: string; created_at: string; job_id: string; tasks: { id: string; sample_id: string; question_id: string; category: string; task_type: string; input_hash: string; model: { name: string } }[]; parent_run_id: string | null; concurrency: number; max_calls: number; frozen_sample_ids: string[] }
export const emptyContent = (): Content => ({
  title: "新候选样本", category: "chat", language: "zh", platform: "generic", kind: "synthetic", source_text: "",
  source_refs: [], tags: [], original_assets: [], metadata: {},
  messages: [{ id: "m1", speaker: "A", text: "请填写候选消息", timestamp: null, source_refs: [] }],
  questions: [{ id: "q1", question: "请填写题目", task_type: "qa", answer: null, gold: false, message_ids: ["m1"] }],
});
export const labels: Record<string, string> = {
  response_received: "已收到回答", ready: "等待执行", service_failed: "模型服务失败", blocked_upstream: "上游未提供有效预测", blocked_no_match: "未找到合格匹配", invalid_input: "输入无效", completed_with_issues: "执行结束，存在待处理项", aborted: "后续调用已停止",
  queued: "等待开始", running: "进行中", completed: "执行已完成", failed: "失败", unknown: "结果待确认", cancelled: "已取消",
  needs_review: "待人工审核", needs_revision: "需纠正", approved: "人工通过", rejected: "拒绝", pass: "通过", revise: "需修改",
  awaiting_human_review: "等待人工审核", calling_model: "等待模型返回", recorded: "已记录", reject: "不采用", pending: "待定", human: "人工审核", model: "模型评估", correction: "纠错同步", comment: "审核评论", rendering: "渲染中", ready_to_package: "可打包",
};
export const label = (value: string) => labels[value] || value;
export const num = (v: number | null | undefined, suffix = "") => v == null ? "—" : v.toFixed(2) + suffix;

export const stamp = (value: string) => new Date(value).toLocaleString("zh-CN", { timeZone: "Asia/Singapore", hour12: false }) + " SGT";
