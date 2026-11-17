---
name: legal-benchmark
description: Freeze and evaluate existing legal chat screenshot classification, message questions and case VQA against configured vision models, preserving source references and reproducible results.
---

Read `docs/data-contracts.md` and `blocks/evaluator/config.yaml`. Run `python -m legalhub.benchmark prepare` after the image inventory exists.

Use exact vision model IDs from the selected provider. Configure cloud or local mode and credentials outside tracked source. Old configs contain text-only models too; do not assume every configured model accepts images. Run the evaluator without `--execute` first to check the task/image count and model settings.

Once the user's endpoint, model scope and spending constraint are known, run the selected tracks. The `--execute` flag calls the provider; without it no requests are sent. Use `--output` to resume the same configuration. Keep failed and invalid responses in the report denominator.

Report all eight tracks independently, including evidence form, chat type and single-image case analysis. The original assisted message prompts contain model-extracted text. Grounded message prompts retain only the target label and manual image coordinates. Case open-answer text overlap is a proxy, not legal correctness. Do not select a professional evidence model using that proxy alone.

Preserve planned task IDs, raw responses, usage, latency, model identity, prompt hash and dataset digest. Archive multiple models on the same dataset and publish `reports/v1.0.0_model_evaluation.md`. Keep legacy KIE metrics separate from VQA and new SOTA comparisons.
