# Reproduction in this repository

There are three different reproducibility claims:

1. **Artifact verification:** compare source, prompts, code, authoring outputs, claims and image SHA256. This should work offline with the archived repository.
2. **Pipeline replay:** reassemble normalized cases and rerender the archived authored messages with the documented Python/browser/font environment. This does not call a language model. Byte-identical PNGs require the same browser, fonts and platform; check layout and content independently as well.
3. **Generative replication:** ask a model to author new drafts under the same protocol. This round used runtime Codex agents; the exact model build and sampling seed were not exposed. Archived reasoning summaries/reviews are available, hidden reasoning is not. Exact regeneration is not guaranteed. Do not publish invented temperature, seed, provider model name or human review scores.

The cohort config records `agent` execution. The repository's older `legalhub.synthesis.model/call` and model configs implement cloud/local endpoints; changing a config enum does not make the offline claim builder an inference runner. For a new cloud/local round, record endpoint model identifier, parameters, model/prompt hashes, response metadata and raw outputs in a separate directory; never include API secrets in a paper bundle. The fourth-round scripts do not call a paid API.

## Verify current archived cohort

From the repo root:

```powershell
.venv/Scripts/python.exe tools/v2_claim_support.py verify
```

The checker verifies original source text spans, claim citations, visible message coverage, 860×1864 PNG size, local HTML references, answer-field exclusion from tasks, and unchanged previous-round files. It also verifies that corrupted source offsets and nonexistent citations are rejected. It does not establish legal label correctness or source authenticity from pixels alone.

## Replay a separate cohort without overwriting reviewed work

Choose a new `datasets/v2.0.0/<round>` path. Copy the contents of `round_004/frozen_authoring/` into the new cohort's `authoring/` and copy `config.json`; preserve each source's archive provenance. `frozen_authoring_manifest.json` records the final root-reviewed replay inputs, while original author drafts and revisions remain under the original `authoring/` and `zh/`. Then run:

```powershell
.venv/Scripts/python.exe tools/v2_claim_support.py inventory --out datasets/v2.0.0/round_replay
.venv/Scripts/python.exe tools/v2_claim_support.py build --out datasets/v2.0.0/round_replay
.venv/Scripts/python.exe tools/v2_claim_support.py render --out datasets/v2.0.0/round_replay
.venv/Scripts/python.exe tools/v2_claim_support.py verify --out datasets/v2.0.0/round_replay
.venv/Scripts/python.exe tools/check_v2_chat_layout.py --out datasets/v2.0.0/round_replay
.venv/Scripts/python.exe tools/v2_claim_support.py bundle --out datasets/v2.0.0/round_replay
```

Internet-source archive paths in frozen authoring may refer to the original cohort. This is valid provenance, provided they are read-only and their hashes match; the builder must not require moving or silently rewriting those sources. Before sharing a replay, include the referenced web snapshots. For the actual round, root corrections in `root.review.json` and `root.versions/` are reviewed final inputs; copy final reviewed `case.json` and `claims.review.json` into replay authoring's revised inputs when reproducing final artifacts rather than authors' pre-root versions. Preserve draft and second-pass records separately.

The renderer checks both renderer-code and visible-input hashes. Calling render after either changes regenerates the affected screenshots and archives old PNGs; changes to answer text alone refresh tasks and pages. `freeze` exports the current reviewed inputs; call `bundle` after reports and validation are final.

Current acquisition commands:

```powershell
.venv/Scripts/python.exe tools/v2_acquire_claim_sources.py prepare
.venv/Scripts/python.exe tools/v2_acquire_claim_sources.py fetch
```

`prepare` creates a candidate review queue and unexecuted search plan; `fetch` retrieves only explicit seed URLs, retaining failures. HTML response success is not full-judgment or dialogue acceptance. Replay uses archived snapshots; do not refetch them and claim the website is unchanged. SSL/access failures remain recorded, without bypassing authentication.

## Paper bundle

Keep `config.json`, `environment.json`, `artifact_manifest.json` and its hash, source hashes and retrieval records, selection/rejection records, full-reading ledgers, drafts and revisions, root/peer revisions, messages/images/page mappings, answer-free task inputs and reviewer labels. Preserve source licensing/access limits separately. Raw official judgments and authored court commentary can have different reuse requirements; dataset redistribution needs source review, not just a reachable URL.

`bundle` hashes maintained tool/skill files and cohort artifacts, records actual installed package versions and Chromium binary hash. It records the available Git HEAD as a base version, but the generated artifacts and edits need their own hashes because they may not be committed. It pins the Python replay dependencies in `requirements.replay.lock.txt`; Microsoft fonts and the browser binary are not embedded, so environment portability remains a stated limitation. Keep unknown model identifiers explicit.
