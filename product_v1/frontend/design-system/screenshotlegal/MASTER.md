# ScreenshotLegal UI/UX design system

Updated: 2026-10-25. Scope: product_v1 React frontend.

## Product boundaries

Keep four independent entry points and their existing features:

| Product | Route | Existing responsibility |
| --- | --- | --- |
| Case Workbench | / | Overview, case editing, image evidence timeline, mock PPT |
| Evaluation Lab | /evaluation.html | Model configuration, KIE/VQA workflows, fixed-release evaluation and results |
| Data Studio | /studio.html | Generation batches, generation rules/history, quality comparisons |
| Review Desk | /review.html | Sample/region review, corrections, comments, quality rules and publication |

Operations, audit and the legacy console remain reachable. Domain schemas, APIs, permissions, budgets, draft persistence, release rules and rendering geometry stay unchanged.

## Direction and research

Use a professional legal workspace: ink navy navigation, warm neutral canvas, white working surfaces and restrained gold accents. Prioritize legibility, traceability and action hierarchy.

The ui-ux-pro-max search verified the Legal Services palette direction (navy and gold), Accessible & Ethical style, and React semantic-control guidance. Its generated landing-page pattern remained sales-oriented after a narrower retry, so it was not adopted or persisted. The workspace layout follows the existing product structure and general dashboard guidance. Do not add marketing sections, security claims, certification badges or fabricated metrics.

## Source of truth

- Semantic tokens: src/design-system/tokens.css.
- Shared controls: src/components/ui/index.tsx.
- SVG icons and brand mark: src/components/icons/index.tsx.
- Product switching: src/components/shell/ProductHeader.tsx.
- Shared layout and controls: src/styles/app.css.
- Research layouts: src/styles/research.css.

No additional runtime dependency, remote font request or image asset is required.

## Palette

| Token | Value | Role |
| --- | --- | --- |
| --background | #f5f4f0 | Warm page canvas |
| --surface | #ffffff | Forms and cards |
| --surface-subtle | #fafaf8 | Read-only surfaces, table headings |
| --text | #253340 | Primary text |
| --muted | #5c6873 | Supporting text |
| --primary | #243e53 | Primary actions and active elements |
| --primary-hover | #182e40 | Primary action hover |
| --accent | #8b642e | Eyebrows, restrained icon accents |
| --sidebar-background | #192e3e | Case navigation |
| --sidebar-text | #f1f4f6 | Text on dark navigation |
| --sidebar-muted | #bbc8d2 | Secondary navigation text |
| --sidebar-accent | #d4b47c | Active indicator and focus on dark surfaces |
| --control-border | #87949e | Visible input boundaries |
| --border | #dcdedc | Decorative card separators |

Success, warning, danger and info each have foreground and soft-background tokens. Always preserve a text label with a status; color does not convey a result by itself. Completion status never implies legal certification.

## Typography and spacing

Use the local system sans-serif stack for Chinese and dense working content. Georgia is limited to the Latin wordmark. Headings use 27–32px; section titles use 18px; desktop body text uses 14px with a 1.65–1.85 line height. Form labels and table cells use 13px. Small eyebrows and metadata are supplementary, never the sole instruction.

Use the 4/8px spacing rhythm: 8px control gaps, 16–24px grouping, 24–36px section separation. Radius: 6px controls, 10px cards. Shadows remain subtle. Data uses tabular figures.

## Navigation and responsive behavior

The shared top bar switches products. The context bar keeps workflow/audit links separate from product navigation. Case search and selection sit with the case sidebar instead of crowding the product header.

Desktop case navigation remains a sidebar. At 720px and below it becomes a two-column navigation group; case selection and case creation use native details disclosures. Opening either panel preserves all original fields and actions. At 1250px and below product switching wraps to its own row. Research grids collapse without removing controls. Wide tables scroll inside their own bounded, keyboard-focusable wrappers.

Validate 375, 768, 1024 and 1440px; also check landscape, longer names and English text.

## Interaction and accessibility

- Buttons expose primary, secondary and ghost variants. Preserve native form submission semantics.
- Primary actions: save, create/submit, start evaluation and generation. Secondary actions: inspect, cancel, discard and navigation.
- Inputs retain visible labels, native validation and password-manager autocomplete.
- Use native buttons, links and details; icons are decorative SVGs with aria-hidden.
- Focus rings: 3px with offset; dark navigation uses the gold focus token.
- Both application shells include a keyboard skip link to their focusable main region.
- Workbench tab changes focus the new content.
- Honor prefers-reduced-motion; no business process depends on animations.
- Preserve exact screenshot dimensions and region-coordinate calculations. Geometry hit areas and handles are exempt from generic button minimum heights.
- Keep draft, conflict, stale-image, unknown-result, budget and mock-PPT notices truthful and visible.

## Change discipline

Edit shared tokens/components first. Feature modules must not hardcode colors or import third-party UI vendors directly. Keep legal content, model settings, fee authorization and publication behavior intact. Validate functional regression in an isolated data directory.
