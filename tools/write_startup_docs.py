from pathlib import Path
import json
H=Path(__file__).resolve().parents[1]
P=H/'projects'
requirements={
'ScreenshotLegalBench_v2':'pandas\nopenpyxl\nrequests\nbeautifulsoup4\nPyYAML\nopenai\ntqdm\nJinja2\nPillow\nlxml\n',
'llm_evluator':'fastapi\nuvicorn\npydantic\nrequests\nrequests-toolbelt\npandas\nopenpyxl\nnumpy\nscipy\nscikit-learn\nPyYAML\nopenai\ntqdm\nJinja2\nPillow\nplaywright\npython-dotenv[cli]\ntzdata\n',
'Batch':'requests\nbeautifulsoup4\nlxml\n',
'crawler-law':'requests\nbeautifulsoup4\nmysql-connector-python\npymongo\npandas\nopenpyxl\nselenium\nundetected-chromedriver\nwebdriver-manager\nchardet\ntqdm\n',
'quiz-collector':'Flask\npandas\nopenpyxl\nPyYAML\nopenai\ntqdm\nJinja2\n'}
setup='''## 环境准备（PowerShell）

在本项目目录执行：

```powershell
py -3.12 -m venv .venv
.\\.venv\\Scripts\\python.exe -m pip install -r requirements-hub.txt
```

`requirements-hub.txt` 根据当前代码 import 整理，是启动依赖清单，不是原实验版本锁定文件。下方命令都使用本项目虚拟环境；不用激活环境。
'''
docs={}
docs['ScreenshotLegalBench_v2']='''# ScreenshotLegalBench_v2 启动说明

作用：主数据构建与评估脚本集；没有统一 Web 服务。

先进入 `screenshotLegalHub/projects/ScreenshotLegalBench_v2`。副本中的已识别旧 Windows／Linux 项目路径已改为从 Hub 根目录定位，原始项目未修改。

'''+setup+'''
## 本地数据处理

这些脚本会重新写出解析或统计产物：

```powershell
.\\.venv\\Scripts\\python.exe describe_data_0811freeze.py
.\\.venv\\Scripts\\python.exe generate_chat/generate_chat_sample.py
```

进入评估子目录再执行标注展开与现有结果匹配：

```powershell
Push-Location process_local_evaluator
..\\.venv\\Scripts\\python.exe 0_generate_evaluate_qa.py
..\\.venv\\Scripts\\python.exe 2_match_iou.py
..\\.venv\\Scripts\\python.exe 2_match_iou_v2.py
Pop-Location
```

`0_generate_evaluate_qa.py` 读取当前子目录的 `screenshot_legal_annotations (1).json`；统计脚本读取根目录另一个标注版本。二者不能混用为同一冻结版本。`2_match_iou_v1.py` 有函数名不一致，问题导出使用 v2。

## 聊天生成与 KIE 推理

先在 `generate_chat/config_full.yaml`、`process_local_evaluator/config.yaml` 核对模型别名、模型名、API Key 与服务地址，再执行：

```powershell
.\\.venv\\Scripts\\python.exe generate_chat/batch_infer_v2.py
Push-Location process_local_evaluator
..\\.venv\\Scripts\\python.exe 1_run_infer_kie_gt.py --config config.yaml --models qwen2_5_vl_32b --prompt-file kie_prompt.md --images-dir images --output-dir output --funnel-iterations 0
Pop-Location
```

上述命令会调用模型。KIE 的 `images` 输入目录已随项目复制；运行前核对其截图范围与所选标注版本是否一致。`batch_infer_v2.py` 默认提示词是 `prompt_v0.md`；需要 v1 时应修改其 `PROMPT_MD_PATH`，并单独命名结果，避免覆盖历史产物。

## 英国案例采集

```powershell
.\\.venv\\Scripts\\python.exe uk_crawaler/main.py
.\\.venv\\Scripts\\python.exe uk_crawaler/detail.py
```

从项目根目录运行，这样 `case_search_results` 相对目录一致。这两条命令访问案例网站并写出采集结果。

## 截图原型

`generate_wechat_shot.py` 使用 Pillow，运行前需设置实际中文字体 `FONT_PATH`。更完整的浏览器截图脚本见相邻 `llm_evluator/启动说明.md`。本次仅复制并校验图片资源，没有查看或解析图片内容。
'''
docs['llm_evluator']='''# llm_evluator 启动说明

作用：多模型生成质量评分、人工／模型一致性分析，以及微信与 WhatsApp 截图自动化。进入 `screenshotLegalHub/projects/llm_evluator`。

'''+setup+'''
## 评分服务

推荐入口是带 RPM 控制的 `main_v3_rpm.py`；兼容入口为 `main_v3.py`。在 `config.yaml` 核对模型配置，在 `feishu_utils.py` 核对现存飞书配置。代码没有自动加载 `.env`；需要该文件的环境变量时使用下面的 dotenv 启动方式：

```powershell
.\\.venv\\Scripts\\python.exe -m dotenv run -- .\\.venv\\Scripts\\python.exe -m uvicorn main_v3_rpm:app --host 127.0.0.1 --port 18321
```

若不需要 `.env`，可直接：

```powershell
.\\.venv\\Scripts\\python.exe -m uvicorn main_v3_rpm:app --host 127.0.0.1 --port 18321
```

健康检查 `http://127.0.0.1:18321/health`，接口说明 `http://127.0.0.1:18321/docs`，任务入口 `POST /run`。启动时会建立事件工作队列；实际评分任务会调用模型，并按原代码向飞书上传或通知。

主要输入为 `_merged/human_merged.xlsx`。`input/wkinfo_samples_with_inference.jsonl` 当前只有 `key/idx/ts/response`，缺少判决映射字段；模型评分将依赖合并表 `content` 回退。正式运行前应核对正文及人工评分列；迁移没有伪造这些缺失字段。

## 分析脚本

```powershell
.\\.venv\\Scripts\\python.exe human_score_spearman_count.py
.\\.venv\\Scripts\\python.exe fmt_re_test_v1.py --merged-xlsx _merged/human_merged.xlsx --scored-csv _merged/你的评分结果.scored.csv --out-prefix _merged/hub_analysis
```

替换 `你的评分结果.scored.csv` 为实际文件。前者统计人工分的并列／可区分分布；后者分析排序一致性。`fmt_re_test.py` 是带交叉验证校准的旧实验分析版本。

## 微信截图

```powershell
.\\.venv\\Scripts\\python.exe -m playwright install chromium
.\\.venv\\Scripts\\python.exe wechat_screenthot/generate_chat_screenshots_v6.py --input-root datasets --output-root output_screenshots
```

先准备 `datasets/<会话>/chat.json`，采用 `vue3-wechat-tool` 的 `chatList` 格式；当前默认 `datasets` 目录不存在。浏览器会访问在线生成器，也可通过 `--url` 指向自建实例。

## WhatsApp 截图

```powershell
.\\.venv\\Scripts\\python.exe whatsapp_screentshot/fake_whatsapp_chat.py --jsonl_path 路径/会话.jsonl --headless
```

输入每条必须有 `timestamp/content/role`。生成器输入与主项目 `participants/messages` JSON 不同，需自行准备正确格式。Playwright 浏览器需要按上面的命令安装。
'''
docs['Batch']='''# Batch 启动说明

本 Hub 明确关联的部分是英国判例正文补抓。完整 Batch 源文件也已复制，以保留上下文；其他通用 Google／Gemini 脚本不属于已确认论文链路。

进入 `screenshotLegalHub/projects/Batch`。

'''+setup+'''
## 英国判例正文补抓

```powershell
.\\.venv\\Scripts\\python.exe england_case_caller.py
```

默认输入已定位到本 Hub 的 `england_court_dataset/results.jsonl`。当前 `FIX_ENRICHED_PATH` 指向已有 `results.enriched.jsonl`，因此默认是扫描已有富集结果、修复缺失正文；程序可能覆盖副本中的富集文件并产生备份。需要完整新抓取时，在本项目副本中将 `FIX_ENRICHED_PATH` 设为 `None`，同时核对 `OVERWRITE_INPUT`。

原始与富集文件均有 480 条记录。命令访问案例网站；不会修改原目录中的同名文件。

## 其他历史脚本

原 `requirements.txt` 为旧 Google Vision 工具依赖。这里新增的 `requirements-hub.txt` 只面向已确认关联的英国案例流程，避免把所有旧 Google 依赖当作此流程的启动条件。其他历史服务另需其云端账号、模型配置与对应依赖，不作为统一推荐入口。
'''
docs['labelU-Kit']='''# labelU-Kit 启动说明

作用：图像、视频和音频标注组件及前端任务平台。它是报告中的标注工具候选；具体数据来源仍待确认。

进入 `screenshotLegalHub/projects/labelU-Kit`，安装 Node.js 与 pnpm；当前锁文件为 v9 格式，使用兼容该格式的 pnpm。锁文件已保留，`node_modules`、构建产物与 `.git` 未复制。

## 前端开发服务（PowerShell）

```powershell
$env:HUSKY = '0'
pnpm install --frozen-lockfile
pnpm --filter @labelu/frontend start
```

`HUSKY=0` 适用于没有复制 Git 仓库的源代码快照，避免 prepare 安装 Git hooks。根目录没有通用 `start` 脚本，因此需使用 `@labelu/frontend` 过滤器。前端地址：`http://localhost:3004`。

## 后端依赖

`apps/frontend/vite.config.ts` 将 `/api` 代理到 `http://127.0.0.1:8000`，`/ws` 代理到同端口。当前目录包含前端及组件，没有配套标注后台服务。前端可启动，但任务、账号、数据和导出等完整功能需要另外配置后端；或按实际部署修改代理地址。

本地源文件保留了隐藏部分导出、任务配置、删除和下载按钮的改动，迁移不会恢复这些历史改动。

## 构建与预览

```powershell
pnpm build
pnpm build:frontend
pnpm --filter @labelu/frontend preview
```

预览端口为 3007；静态预览的后端路由需要部署环境另行提供，Vite 开发代理不等于生产后端配置。启动依赖来自现存 package.json 和锁文件，迁移没有执行依赖安装或构建。
'''
docs['silicon-pool']='''# silicon-pool 启动说明

作用：硅基流动 API Key 管理与兼容接口转发。报告中的基础设施候选；未确认原实验实际使用此网关。

进入 `screenshotLegalHub/projects/silicon-pool`。

## Python 本地启动

`pyproject.toml` 指定 Python >=3.12。

```powershell
py -3.12 -m venv .venv
.\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt
.\\.venv\\Scripts\\python.exe main.py
```

管理页面：`http://127.0.0.1:7898`，API 地址：`http://127.0.0.1:7898/v1`。首次启动会在当前目录生成配置／数据库，沿用项目原有默认账号配置。需要供其他项目调用时，再修改其模型 `base_url` 与认证配置；迁移没有自动切换网关。

## Docker Compose

```powershell
docker compose up --build -d
```

副本 `docker-compose.yml` 的源码挂载已从 `D:/silicon-pool:/app` 调整为 `.:/app`。当前端口映射为 `17898:7898`，因此 Docker 模式页面是 `http://localhost:17898`，API 为 `http://localhost:17898/v1`。

停止：`docker compose down`。原始 Compose 文件未修改。
'''
docs['crawler-law']='''# crawler-law 启动说明

作用：2023—2024 年的中国法律与判决数据采集；与主项目 wkinfo 数据来源相关，但尚未确认直接产物衔接。进入 `screenshotLegalHub/projects/crawler-law`。

'''+setup+'''
## wkinfo 采集

运行前先核对：

- `config.py` 的 MySQL／MongoDB 连接与数据库名；外部数据库及数据表需已准备好。
- `crawler.ddl` 的结构是否与目标数据库一致。
- `wkxx.py` 内现存会话凭证是否仍有效；本说明不展示其内容。
- `wkxx.py` 最后几行的实际采集入口。

当前默认执行的是 **法律数据分页采集，从第 21 页开始**，不是判决采集：

```powershell
.\\.venv\\Scripts\\python.exe wkxx.py
```

需要判决采集时，在新目录副本中将最后的 `fetch_law_paginated_results(21)` 改为已有的 `fetch_judgment_paginated_results(1)`，同时核对表和查询参数。代码会访问远程网站并写入所配置数据库。

## 法信与浏览器采集

`faxin*.py`、`crawler.py`、`task_scheduler.py` 属于其他历史采集路径，依赖目标网站登录、Chrome／驱动和数据库。复制的旧 Windows 驱动可作历史资源，但并不代表与现有浏览器兼容。先按所选脚本调整数据库、登录和驱动，再单独运行；没有可无配置启动的统一服务。
'''
docs['quiz-collector']='''# quiz-collector 启动说明

作用：2025 年 12 月的关联延续项目，包含题目生成、人工答题／标注、统计面板及模型评估。进入 `screenshotLegalHub/projects/quiz-collector`。

'''+setup+'''
## 人工答题／标注界面

已有 `data` 和 `images` 随项目复制。先核对 `data/admin.jsonl` 是否是目标基准，再运行：

```powershell
.\\.venv\\Scripts\\python.exe app.py --file data/admin.jsonl --img_dir images --port 5000
```

页面：`http://127.0.0.1:5000`。代码会在副本的 `data` 中创建或更新用户答题数据；账号沿用 `app.py` 的现存配置。本次没有启动服务或触碰原答题数据。

## 统计面板

另开终端，同一项目目录运行：

```powershell
.\\.venv\\Scripts\\python.exe dashboard.py --data-dir data --host 127.0.0.1 --port 5001
```

面板：`http://127.0.0.1:5001`。两个服务原默认都用 5000，这里明确分配 5001 避免冲突。

## 题目生成

```powershell
.\\.venv\\Scripts\\python.exe generator.py
```

读取 `source.json`、`group_source.json`、`multi_choice_source.json`，写出 `data/final_tasks.jsonl`。这会重新生成任务文件，先确认要使用当前输入。

`0_extract_case_of_action.py` 通过模型生成案由和干扰项；`1_gen_psedo_wrong.py` 增补伪错误选项。它们需要指定实际输入／输出和配置，可用 `--help` 查看参数。

## 模型评估的缺失输入

`quality_assuarance_evaluate.py` 的默认评分 Markdown 当前缺失；`eval_modelrefine.py` 默认的 `v2_eval_modelrefine` 问答表也未保存在主项目中。应补齐后再运行，例如：

```powershell
.\\.venv\\Scripts\\python.exe quality_assuarance_evaluate.py --score-md 你的评分提示词.md --config config_full.yaml --in-jsonl ../llm_evluator/input/wkinfo_samples_with_inference.jsonl --in-xlsx ../ScreenshotLegalBench_v2/generate_chat/output/wkinfo_samples_by_case.xlsx
.\\.venv\\Scripts\\python.exe eval_modelrefine.py --input-xlsx 你的问答表.xlsx --out-xlsx 检查后的回答.xlsx --config config_full.yaml --layout-json layout_vqa_case_text_only_merged.json --struct-json ../ScreenshotLegalBench_v2/process_local_evaluator/image_structured_info.json
```

先替换占位文件，核对该配置里实际模型别名并传入 `--model`／`--model-alias`。以上评估会调用外部模型；复制并不能补齐未保存的历史输入。
'''
for name,doc in docs.items():
 root=P/name
 if not root.exists():raise RuntimeError('Copy not ready: '+name)
 (root/'启动说明.md').write_text(doc,encoding='utf-8-sig')
 if name in requirements:(root/'requirements-hub.txt').write_text(requirements[name],encoding='utf-8')
rows=[('ScreenshotLegalBench_v2','确认：主项目','脚本流水线','—'),('llm_evluator','确认：同期关联','main_v3_rpm:app','18321'),('Batch','确认：英国案例子流程','england_case_caller.py','—'),('labelU-Kit','标注工具候选','@labelu/frontend start','3004'),('silicon-pool','网关候选','main.py / Docker Compose','7898 / 17898'),('crawler-law','旧采集工具候选','wkxx.py（需配置）','—'),('quiz-collector','确认关联，2025-12','app.py / dashboard.py','5000 / 5001')]
readme='''# screenshotLegalHub

本目录整理 ScreenshotLegalBench_v2 相关的 7 个项目，包含已确认关联、时间范围外延续项目和待确认候选。源目录与原报告保持保留；此处是独立副本。

## 目录

```text
screenshotLegalHub/
  projects/                 # 七个项目，各有 启动说明.md
  reports/ScreenshotLegalBench_v2/  # 原报告及检索附件的副本
  tools/                    # 迁移、文档生成和校验脚本
  hub_paths.py              # 副本代码的项目路径解析
  migration_manifest.json   # 复制清单、哈希、排除项和路径适配记录
  verification.json         # 迁移核验结果
```

## 项目与启动入口

| 项目 | 关系 | 入口 | 端口 | 启动说明 |
| --- | --- | --- | --- | --- |
'''
for name,relation,entry,port in rows:readme+=f'| `{name}` | {relation} | `{entry}` | {port} | [启动说明](./projects/{name}/启动说明.md) |\n'
readme+='''
## 报告

[项目对应关系说明](./reports/ScreenshotLegalBench_v2/项目对应关系说明.md)，[工作区项目筛查](./reports/ScreenshotLegalBench_v2/工作区项目筛查.csv)，[代码日期清单](./reports/ScreenshotLegalBench_v2/相关项目代码日期清单.csv)。

迁移后的说明文档链接指向 `projects` 副本。JSON／CSV 中的原检索路径保留为历史来源记录。报告目录内旧检索脚本也完整归档，但其中仍有原工作区路径，不作为 Hub 日常启动入口。

## 本次整理内容

- 复制代码、现存配置、数据、图片资源和日志；没有查看图片内容。
- 排除 `.git`、`node_modules`、虚拟环境、Python 缓存、`.cache`、`.next`、`dist`、`build` 和 `.pyc/.pyo`；具体路径见迁移清单。原 Git 历史仍在源目录，依赖及构建产物可重新生成。
- 已识别的代码路径从原 Windows／Linux 项目目录改为 `hub_paths.py` 解析，可随整个 Hub 移动。数据内的历史路径不批量改写。
- 新增各项目启动说明；Python 启动依赖文件依据 import 整理，不宣称重建原实验软件版本。
- 没有安装依赖、启动服务、抓取网站、调用模型或发送飞书消息。校验范围是文件复制、代码语法、路径适配与文档链接；并非完整运行验收。

缺失的历史输入、标注后端、数据库、账号和模型配置要求详见各项目启动说明。迁移没有补造原项目中缺少的实验数据。
'''
(H/'README.md').write_text(readme,encoding='utf-8-sig')
print('STARTUP_DOCS_CREATED',len(docs))
