"""Publish asset readiness, without claiming unexecuted model results."""
import collections
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from legalhub import benchmark as b


def main():
    summary = b.read(ROOT/'reports/restart/inventory_summary.json')
    archive = b.read(ROOT/'reports/restart/archive_inventory.json')
    manifest, tasks = b.dataset()
    check = b.read(b.ART/'check.json')
    if check['dataset_sha256'] != manifest['dataset_sha256']:
        raise ValueError('Run benchmark check for the current dataset first')
    workbooks = [x for x in archive if 'workbook' in x]
    lines = ['# v1.0.0 资产核验与执行边界', '',
             '核验日期：2026-10-04（Asia/Singapore）。原始图片、标注、历史输出和归档未改写。', '',
             '## 图片实际位置', '',
             '| 来源 | 原图数量 | 用途 |', '|---|---:|---|',
             '| `projects/ScreenshotLegalBench_v2/process_local_evaluator/images/` | 1088 | KIE 主图片目录 |',
             '| `projects/quiz-collector/images/` | 1170 个规范文件名 | 人工答题图片，含主目录全部图片及缺的 82 张 |', '',
             f'合并索引：{summary["images"]} 张，损坏 {summary["corrupt_images"]} 张。同名原图已比对 SHA256，无内容冲突。',
             '带 UUID 前缀的副本、缩略图、`images copy`、`images_try` 和 `ploted_images` 不作为新增独立样本计数。',
             '索引保留原始路径与同名副本位置，见 `reports/restart/images_manifest.json`。', '',
             '## 归档中的飞书 Excel', '',
             '已直接只读解析 `归档.zip`，重置错误的 Excel 工作表维度后统计物理行数。行数包含表头及空行，不等于有效评分样本数。', '',
             '| 文件 | 工作表 | 物理行数 | 列数 |', '|---|---|---:|---:|']
    for book in workbooks:
        for sheet in book['workbook']:
            lines.append(f'| {book["name"]} | {sheet["sheet"]} | {sheet["rows"]} | {sheet["columns"]} |')
    lines += ['', '每个源文件的 SHA256、表头和预览在 `reports/restart/archive_inventory.json`。这些表主要是生成/评分 Prompt 迭代、人工评分及错误案例，不能直接充当本轮视觉模型的预测结果。', '',
              '## 现成代码与输入', '',
              '- 旧 KIE 推理：`projects/ScreenshotLegalBench_v2/process_local_evaluator/1_run_infer_kie_gt.py`。',
              '- 旧匹配与题目导出：同目录 `2_match_iou.py`、`2_match_iou_v2.py`。',
              '- 新统一入口：`legalhub/benchmark.py`，已运行 prepare 和 check。',
              '- 现有标注：同目录 `screenshot_legal_annotations (1).json`。',
              '- 消息题：同目录 `message_prompts_evaluate.json`。',
              '- 多图案件题：`projects/quiz-collector/layout_vqa_case_text_options.json`。', '',
              '## v1.0.0 按顺序验收', '',
              '1. 现有图片/评估集真实评测固定视觉模型候选，保存原始回答、分项指标、错误、耗时与用量，完成 `reports/v1.0.0_model_evaluation.md`。',
              '2. 根据第一步结果选默认模型，再实现多图证据理解、retrieve、逐句/图片来源引用及用户原有工作流程。',
              '3. 用真实证据输入启动软件、完成一次检索与理解闭环，给出启动命令和运行证据。', '',
              '先完成以上三项，再做数据集重建、合成数据飞轮和扩展架构。原归档的“类案检索、请求权基础（法条）”需求须保留核对，不能未经确认把 retrieve 缩减为关键词查截图。', '',
              '## LegoFlow 重构方式', '',
              '借鉴 [LegoFlow](https://github.com/LegoX/LegoFlow) 的 block 边界和 config/scripts/artifacts 约定，复用历史代码：curator → evaluator → evidence → reporter。当前前两块有真实入口，后两块等待模型选型。', '',
              '## 尚缺条件', '',
              '- 当前 computer-use 工具返回 No browser is available，未读取这次用户提供的私有项目页面。私有链接不写入报告、不发给其他 agent。',
              '- 模型调用最新状态见 `reports/v1.0.0_model_evaluation.md`；资产核验本身不发送模型请求。']
    lines += ['', '模块架构图、GitHub/论文版本对账、缺口与 v2 飞轮见 [重启架构与缺口](../../docs/RESTART_ARCHITECTURE.md)。']
    (ROOT/'reports/restart/ASSET_RESTART.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    metrics = ['# v1.0.0 模型评测报告（待实跑）', '',
               '**状态：资产冻结与离线检查完成，真实模型评测尚未执行。当前没有 SOTA 排名或最佳模型结论。**', '',
               '## 冻结输入', '', f'数据 SHA256：`{manifest["dataset_sha256"]}`。',
               f'原图 {summary["images"]} 张；任务 {len(tasks)} 条；因缺图排除 {len(manifest["excluded_missing_images"])} 条；哈希与来源检查通过。', '',
               '| 任务 | 题数 | 状态 |', '|---|---:|---|']
    for track, count in manifest['tracks'].items():
        metrics.append(f'| {track} | {count} | 待真实推理 |')
    messages = b.read(b.DATA/'message_prompts_evaluate.json')
    passes = collections.Counter(str(x.get('iou_pass')) for x in messages)
    metrics += ['', '## 评分口径', '',
                '- 各任务分别出分，失败、格式错误、未完成题保留在分母。',
                '- 消息 assisted 含旧模型辅助文本，grounded 只提供截图与人工框；二者分别报告。',
                '- 开放案由答案的文本重合率只作诊断，不能据此声称法律理解正确或选出最佳模型。',
                '- 分类、证据和聊天类型的原标注含少量重复图片记录；当前保留源索引，正式报告需同时披露图片级/案件级统计，避免重复记录权重不明。', '',
                '## 历史产物（只读统计）', '',
                '旧 Qwen2.5-VL-32B 推理与结构化结果各 450 条；不是本轮全量复跑。',
                f'旧消息题 {len(messages)} 条，历史 iou_pass 分布：`{json.dumps(dict(passes), ensure_ascii=False)}`。这是框匹配标记，不是消息属性答案准确率。', '',
                '## 模型比较与选择', '',
                '待确定服务端点、精确模型 ID、候选范围和总预算后实跑。届时填写模型版本、有效覆盖、分项指标、延迟、用量/费用、失败案例和默认模型选择依据。', '',
                '## 软件验收', '',
                '待评测选型后实现并实际启动。目前尚未完成 v1.0.0。']
    destination = ROOT/'reports/v1.0.0_model_evaluation.md'
    # Never erase an actual evaluation report during an asset-only refresh.
    if not destination.exists() or '模型评测报告（待实跑）' in destination.read_text(encoding='utf-8'):
        destination.write_text('\n'.join(metrics)+'\n', encoding='utf-8')
    print('Published ASSET_RESTART.md and evaluation readiness status')


if __name__ == '__main__':
    main()
