---
name: legal-synthesis
description: Generate research chat datasets constrained by Chinese or English judgments, preserve quoted chat origins, and render fixed-size WeChat or WhatsApp screenshots for v2 experiments.
---

This skill belongs to v2. Do not invoke it as a substitute for completing v1's existing-data benchmark and working evidence software. Read `docs/data-contracts.md` and archived generation prompts before experimenting.

Extract judgment facts, actors, chronology, quoted chat and unresolved facts. Label verbatim quotes, judgment paraphrases and synthetic additions separately. Generate plausible conversations that satisfy those constraints without placing the judgment's outcome in the screenshots as an answer cue.

Use Chinese judgments for WeChat and English judgments for WhatsApp while retaining the applicable jurisdiction. Create multi-image/cross-conversation evidence dependencies deliberately. Freeze viewport, font, scale and pagination settings; retain rendering IDs and message-to-image bounding boxes.

Keep candidate prompts/versioned runs and generated chat JSON. Compare candidates against human-reviewed constraints and the calibrated rubric. Same-judgment derivatives stay in one split. Publish only reviewed candidates; never present synthetic screenshots as original evidence.
