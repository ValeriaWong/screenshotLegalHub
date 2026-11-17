---
name: judgment-chat-dataset
description: Build and audit reproducible legal chat screenshot datasets from Chinese or English judgments, including claim-support evaluation and source-grounded revisions. Use for this repository's dataset flywheel; preserve source evidence, separate court outcomes from image-only labels, and archive generation inputs and outputs.
---

# Judgment chat dataset

Work from this repository root. Keep each round in its own `datasets/v2.0.0/<round>/` directory. For authoring and claim labels read [the protocol](references/protocol.md); for execution and paper artifacts read [reproduction](references/reproduction.md).

## Choose the dataset track

The source-grounded rules below apply to **original-communication reconstruction**. On 2026-11-06 the user also authorized a separate **fact-constrained synthetic** track for judgments without disclosed chat content. For that track read [fact-constrained synthesis](references/fact-constrained.md): fictional dialogue may be the scored evidence, but must never be presented as a quotation or reconstruction of original chats. Keep its files, counts and evaluation labels separate. Both tracks derived from one judgment must share the same split-group identifier.

## Source and authoring decisions

- Read the complete judgment, including appeal reasoning and result. A party's proof purpose, the court's factual finding, the content of a communication, and its legal effect are different attributes.
- Keep original text and SHA256 unchanged. Verify sender, recipient, medium, date precision and source spans in context. Repeated short quotes need explicit offsets: the first matching “好” may be the wrong speaker or date.
- Court rejection does **not** exclude a source. A concrete but weak chat is useful for claim-support tasks. Missing communication text is a reconstruction gap; do not invent decisive content and call it judgment evidence.
- Preserve quoted typos; mark factual paraphrase, synthetic connective text, and reconstructed attachments separately. Do not move testimony, pleadings, bank transfers, calls or document dates into chat without a communication anchor. Synthetic connective text cannot be the sole evidence for a scored claim.
- Use natural short messages when supported. One authentic message is preferable to fabricated mutual assent. Do not add receipt, consent, payment completion, authorship or precise time to make the evidence complete.
- Save `source.reading.json`, `direct.draft.json`, `direct.revised.json` and `codex.review.json`, including no-change results. Keep previous versions before root corrections. Record actual author/model information; do not inherit the historical Kimi attribution produced by the legacy normalizer.

## Claim support

Use `supported`, `contradicted`, `insufficient` for a **specific proposition and supplied evidence set**. Unknown is not false. Rejection or identity dispute in a judgment is not necessarily visible in an image. Add supported controls alongside non-support probes; require direct opposite evidence for contradicted. Include the insufficiency reason, cited messages/pages and missing evidence in reviewer outputs.

Model inputs include only claim/instruction/images, plus explicitly declared context for `case_context`. Exclude answers, judgment text, fact ledgers, source references, labels and hidden identities from `image_only` tasks. Reviewer pages intentionally show the source and answers and must not be sent to evaluated models.

## Execute and check

The reusable offline entry point is `tools/v2_claim_support.py`: `inventory`, `build`, `render`, `report`, `verify`, `bundle`. `tools/v2_acquire_claim_sources.py` records candidate queues and official webpage snapshots. Read the reproduction reference before executing: authoring is an archived input stage, not a deterministic model regeneration claim.

Use source-disjoint authoring folders when agents are explicitly authorized. One coordinator owns shared manifest, rendering and final validation. Keep V1 and previous V2 rounds unchanged; verify their frozen file hashes.

Render native WeChat/WhatsApp HTML rather than image-generating text. Verify message coverage, stable chrome, card bounds, source coordinates, all local links and image dimensions. Multiple crops of one long message do not demonstrate multihop reasoning. Do not advertise professional gold or difficulty until independent legal review and model blind tests exist.

Before reporting completion, distinguish queued sources, fetched webpages, full judgments reviewed, new cases rendered, reused chats with new questions, claim counts, cause counts and verified negative cases. A target of 200 cases is neither 200 causes nor 200 completed cases.
