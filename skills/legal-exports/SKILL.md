---
name: legal-exports
description: Export legally meaningful chat events to Excel with message and screenshot-page sources, and produce a timeline presentation from the same event table.
---

Read `docs/data-contracts.md`. Implement this stage after the evidence pipeline and use the spreadsheet/presentation skills available in the active environment. This repository does not yet contain an exporter.

Excel rows include event, displayed/inferred time and precision, speaker, main intention, exact quote, all evidence page numbers, message/source links and review status. Retain multiple citations for events spanning screenshots. Provide useful filtering without dropping adverse items from the full export.

The timeline PPT consumes the same event table. Distinguish uncertain dates and conflicts visually, put readable evidence references beside events, and preserve chronology without inventing precise dates. The user's future PPT aesthetics skill should be applied as a presentation adapter without changing facts or sources.

Verify the saved workbook values and page references, render presentation slides and inspect layout. Report whether the export used current model extraction, imported historical results or fixtures.
