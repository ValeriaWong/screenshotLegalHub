---
name: legal-quality-loop
description: Restore Feishu human scores, audit screenshot/question quality and reasoning difficulty, and calibrate generation and evaluation prompts on development data for the legal dataset flywheel.
---

This is v2 work. Read `reports/restart/archive_inventory.json`, the archived scoring notes and `docs/data-contracts.md`.

Map human scores by case, generation/prompt version and annotator; preserve missing values and individual scores before computing agreement. Separate generation faithfulness and plausibility from question answerability, source grounding and reasoning difficulty.

Tag required image count, conversation count, evidence-hop count, distractors, uncertain chronology, identity ambiguity and contradictory submissions. Validate minimal evidence sets. Many images do not by themselves establish multi-hop reasoning. Record when even a professional cannot uniquely answer from the available screenshots.

Tune prompts on a judgment-grouped development split using paired candidates and expert review. Calibrate the scoring model against human disagreement, ranking and absolute score errors. Reserve the frozen test split for reporting; do not tune generator or grader from its errors. Feed development failures to the candidate pool and release each reviewed dataset as a new immutable version.
