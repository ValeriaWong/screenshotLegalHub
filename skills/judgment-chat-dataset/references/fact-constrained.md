# Fact-constrained synthetic chat

The user explicitly approved this separate track: “允许，和原文还原集分开保存”. This permits writing plausible dialogue from judgment facts when original chat text is unavailable. It does not permit attributing invented words to the actual parties as historical evidence.

Use `datasets/v2.0.0/fact_constrained_20261106/`. Preserve original judgments and every prior source-grounded artifact. Use `fc_<source_document_id>` for new cases, `dataset_track: fact_constrained_synthetic`, `is_original_chat_reconstruction: false`, `split: development`, and `source_judgment_id`/`split_group_id` equal to the source document ID. Related trial/appeal families still need linkage before a held-out release.

## Read and write

Read the complete judgment. Build a fact ledger with literal source spans and `court_finding`, `party_allegation`, `disputed`, or `procedural_fact` statuses. Preserve settled material facts and outcomes; allegations remain allegations. Do not use the court's conclusion as the answer to an image-only question.

Create a plausible alternative communication history that fits those constraints. Use fictional display names and natural Chinese WeChat or English WhatsApp exchanges. Chosen send times, platform, dialogue wording, and incidental coordination are scenario assumptions, not claims about the source. Record each assumption. A sparse judgment can support a modest scene; do not manufacture complexity that changes the material dispute.

Prefer short everyday turns, different speaker habits, ordinary requests, partial answers and realistic changes of topic. Participants must not helpfully recite every amount, date and legal issue for the evaluator. Include cross-session references only where the story needs them. Never turn a missing acceptance, payment, authorization, or causal link into an unmarked settled fact. Bounded statements about those matters may appear as allegations or requests.

Keep contact/group titles ordinary and short; the renderer supplies the fiction disclosure in the footer. A participant name in reviewer metadata is not automatically visible in a one-to-one screenshot. Claims should use visible contact names or left/right descriptions unless the image establishes the speaker identity.

Save `source.reading.json`, an actual `direct.draft.json`, `direct.revised.json`, `claims.json` and `codex.review.json`. Each message has `origin_type: fact_constrained_synthetic`, `source_refs: []`, `fact_ids` and `assumption_ids`; source spans belong to the fact ledger, not to fictional message wording. Timestamps use `date_basis: synthetic_scenario` and `minute_basis: synthetic_scenario`. The entire screenshot visibly says it is fictional research synthesis.

## Assess the displayed story

Claims use `answer_basis: synthetic_screenshot_only` and exact `evidence_refs: [{message_id, quote}]`. Labels describe what the synthetic screenshot supports, contradicts, or leaves insufficient. A fictional message is valid evidence within this explicitly fictional task; it is not evidence about the actual lawsuit. Unsupported conclusions from hidden judgment text remain errors.

Include supported controls and insufficient-evidence probes. Add contradicted only for explicit opposite content. Aim for at least one substantive question combining messages across sessions, with a concrete necessity explanation; keep the difficulty unverified until blind model evaluation. No question requires knowing reviewer-only aliases, undisplayed roles, court findings, or assumptions.

An independent agent reads the full source, checks the fact/assumption boundary, naturalness, exact message quotations and every image-only label, and views the actual PNGs. Retain corrections before accepting them. Professional gold and minimum evidence certification remain false.

## Schema and execution

The case keeps the standard participants/conversations/messages shape, plus:

```json
{
  "id": "fc_zh_or_en_source_id",
  "dataset_track": "fact_constrained_synthetic",
  "is_original_chat_reconstruction": false,
  "source_judgment_id": "zh_or_en_source_id",
  "split_group_id": "zh_or_en_source_id",
  "split": "development",
  "facts": [{"id":"f1","text":"A bounded fact","status":"court_finding","source_refs":[{"source_id":"p0001","quote":"literal text","char_start":0,"char_end":12}]}],
  "assumptions": [{"id":"a1","description":"Fictional carrier, aliases or timing","rationale":"Why the scene needs it"}]
}
```

Each claim contains `id`, `claim`, `label`, `task_mode: image_only`, `answer_basis`, `answer`, `reasoning`, `evidence_message_ids`, literal `evidence_refs`, `missing_evidence`, `insufficiency_type`, and `reasoning_steps`. Keep `source_refs` absent or empty on claims. A `cross_session` claim also needs `necessity_rationale` explaining the contribution of each conversation.

`tools/v2_fact_constrained.py check --folder <author folder>` validates this schema. It uses its own validator: do not disguise invented messages as `judgment_paraphrase` to pass the original reconstruction checker. Render and report through this separate tool. Count each source once across tracks when reporting distinct judgments; do not pool benchmark scores from both tracks without identifying the track.
