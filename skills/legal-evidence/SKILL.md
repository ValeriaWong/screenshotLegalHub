---
name: legal-evidence
description: Implement and operate case-level retrieval and event extraction from multiple WeChat or WhatsApp screenshots, with speakers, intentions, time and message-level evidence sources.
---

Read `docs/data-contracts.md` before implementing it. The user explicitly authorized retrieval development alongside evaluation. Build the code-driven retrieval pipeline now; keep final model selection tied to evaluation. Use the vision-model adapter for extraction only and retain the cloud/local switch. Retrieval queries must not call a model.

Assign image IDs, submitted evidence pages and conversation IDs from the input manifest. Extract verbatim messages with original-pixel bounding boxes. Preserve displayed time, precision and uncertainty separately from inferred chronology. Keep speaker identity local to each conversation until supported by evidence.

Build events from linked messages and produce source references for every event and quote. Retrieval searches the current case's messages/events/images and returns those references. Cross-conversation event links must retain their supporting messages. Validate that citations refer to actual input images and that quoted text is grounded; store unresolved alignment and chronology for review.

Route judge reconciliation to `legal-reconcile`, party-relative analysis to `legal-lawyer-review`, and final exports to `legal-exports`. Distinguish actual model extraction from imported historical predictions and demonstration fixtures in the run metadata.
