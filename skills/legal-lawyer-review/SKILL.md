---
name: legal-lawyer-review
description: Mark extracted chat evidence as favorable, adverse, neutral or uncertain relative to a specified client party, and build reviewable lawyer work views with traceable sources.
---

Read `docs/data-contracts.md`. This stage is planned for v1 and requires the evidence extraction output.

Determine the client party and the claims being assessed from the case configuration. For each event, identify helpful facts, adverse admissions, contradictions and missing context. Explain the assessment using quoted messages and evidence pages. Keep uncertainty visible when the screenshots do not resolve the issue.

Support review labels and filtered lawyer work views while preserving the complete original evidence and full extraction table. Filtering an output view must remain distinguishable from changing a source record. Do not implement deletion or alteration of original evidence to conceal adverse records.

Publish all events with party-relative assessments and review status; filtered views must retain links to the full table.
