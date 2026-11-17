---
name: legal-reconcile
description: Align two parties' submitted chat screenshots in judge mode, combine overlapping evidence, identify gaps and conflicts, and reconstruct the most complete supported conversation.
---

Read the Reconciliation and SourceRef contracts in `docs/data-contracts.md`. This stage is planned for v1 and has no executable implementation yet.

Retain each party's page numbering and provenance. Identify candidate overlaps using message content, layout, speakers and displayed time. Confirm links using the surrounding sequence; identical short messages alone are insufficient. Merge supported duplicates into a canonical message with all source references.

Restore only content visible in the submitted material. Represent missing turns as gaps, and disagreement as conflicts. A fuller screenshot can fill a cropped area when an overlap is confirmed. Never use synthetic-generation output to fill missing real evidence.

Publish the reconstructed sequence, page crosswalk, gap/conflict records, uncertain identity links and source-preserving event table. Judge mode does not rank events for a favored party.
