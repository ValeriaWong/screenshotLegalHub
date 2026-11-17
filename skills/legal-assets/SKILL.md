---
name: legal-assets
description: Inventory ScreenshotLegalBench files, images, Feishu exports and historical VQA assets, reconcile their versions and list missing inputs. Use for asset integration before evaluation.
---

Work from the screenshotLegalHub root. Read `docs/data-contracts.md` and `reports/restart/ASSET_RESTART.md` before changing adapters.

Run `python tools/restart_inventory.py` to validate image files and regenerate local manifests. It reads original assets and writes only `reports/restart/`. Feishu XLSX dimensions can be wrong: reset read-only dimensions and count physical rows. Keep sheet names and source hashes.

For GitHub assets, use the authorized connector. Record repository/tree/blob identifiers and save only the relevant source files. Count distinct image blobs separately from image paths, since historical output folders duplicate originals. `wechat_screen_vqa_dataset/test.json` is COCO detection data, not VQA ground truth.

Private ChatGPT project links belong to this project only. Do not send their URLs or content to other agents or external services. If browser access fails, record the failure and use locally archived documents with explicit provenance.

Publish image/source manifests, concrete missing file names, version mismatches and next executable step. Do not infer dataset difficulty or performance from file counts.
