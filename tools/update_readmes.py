from pathlib import Path
import re,json,hashlib,shutil
H=Path(__file__).resolve().parents[1];P=H/'projects';guide_name='启动说明.md'
info={
'ScreenshotLegalBench_v2':('主数据构建与截图理解实验','''```text
generate_chat/             判决 CSV → 案由抽样 → 聊天生成
uk_crawaler/               英国案例搜索、详情补充
case_search_results/       英国案例数据
process_local_evaluator/   人工属性展开、KIE、IoU、问题导出
screenshot_legal_annotations.json  人工标注的一个版本
describe_data_0811freeze.py        分类与属性统计
generate_wechat_shot.py           Pillow 截图原型
```''','输入为判决 CSV 和人工标注；输出为聊天生成结果、消息框与问题级评估数据。聊天质量评分由相邻 llm_evluator 承担。'),
'llm_evluator':('质量评分、人工一致性分析及截图自动化','''```text
main_v3_rpm.py / main_v3.py  FastAPI 评分服务
feishu_event_sync.py         事件接收与任务队列
feishu_utils.py              飞书记录、附件与通知
input/                      评分输入
_merged/                    人工评分合并表和评分输出
fmt_re_test*.py              相关性、排序与校准分析
wechat_screenthot/           Playwright 微信截图
whatsapp_screentshot/        Playwright WhatsApp 截图
```''','服务读取人工评分表和候选聊天，调用模型评分，输出本地结果并按现存工作流写回飞书；截图生成是独立脚本，不由评分服务自动触发。'),
'Batch':('英国案例全文富集；另保留通用批处理历史代码','''```text
england_case_caller.py       读取案例链接、补抓全文、修复缺失正文
england_court_dataset/      原始及 enriched JSONL
requirements-hub.txt        英国案例流程的启动依赖
其他 *_caller / *_processor 通用历史模型与上传脚本
```''','已确认关联的是 480 条英国案例及正文补抓，输入来自主项目 uk_crawaler 的数据；其他历史脚本不是这一流程的必需服务。'),
'labelU-Kit':('人工标注前端与组件库，具体论文部署待确认','''```text
apps/frontend/              标注任务前端（Vite / React）
apps/frontend/vite.config.ts /api 与 /ws → 外部 8000 端口
packages/                   图像、音视频、格式转换和 React 组件
pnpm-workspace.yaml         pnpm 工作区
pnpm-lock.yaml              前端依赖锁文件
```''','这里只有前端和标注组件，完整任务平台还需要独立标注后端。它与主项目标注格式兼容，但数据来源没有直接确认。'),
'silicon-pool':('模型 API Key 管理与转发候选','''```text
main.py                    FastAPI 主入口（7898）
routers/                   管理和模型代理路由
config.py / db.py          当前工作目录下的配置与数据库
static/                    管理界面
Dockerfile                 Python 容器构建
 docker-compose.yml        宿主机 17898 → 容器 7898
```''','调用方可以把模型 base_url 指向本服务，但目前实验配置仍是直接服务商地址；无需为所有实验先启动网关。'),
'crawler-law':('旧法律／判决数据采集候选','''```text
wkxx.py                    wkinfo API 分页采集
faxin*.py                  法信采集流程
crawler.py / task_scheduler.py 浏览器采集与任务调度
config.py                  外部数据库配置
crawler.ddl                历史数据库结构
chromedriver-win64/        旧浏览器驱动资源
```''','依赖目标网站登录和外部数据库。wkxx.py 默认采集法律条文，不是判决；如需判决，需修改副本的入口。'),
'quiz-collector':('后续题目构建与人工答题（2025 年 12 月）','''```text
app.py                     Flask 人工答题／标注界面
 dashboard.py              Flask 统计面板
generator.py               单图题、排序题、多选题组合
0_extract_case_of_action.py 案由与模型干扰项
1_gen_psedo_wrong.py        错误选项补充
eval_modelrefine.py         模型回答补充
quality_assuarance_evaluate.py 聊天质量评分
data/ / images/            任务、答题记录与图片资源
```''','题目生成、人工答题、统计面板和模型评估是可分别运行的入口；统计面板使用 5001 端口，以免与答题界面的 5000 冲突。')}
root='''# screenshotLegalHub

本目录集中整理 7 个 ScreenshotLegalBench_v2 关联／候选项目。下面直接给出架构、执行顺序、环境准备和各项目启动命令。源项目与原报告仍保留在原目录。

## 1. 项目架构

```text
screenshotLegalHub/
├── projects/
│   ├── ScreenshotLegalBench_v2/ 主实验：判决处理、聊天生成、KIE 与评估问题
│   ├── llm_evluator/            质量评分、人工一致性和截图自动化
│   ├── Batch/                   英国判决全文补抓
│   ├── labelU-Kit/              标注前端与组件（候选）
│   ├── silicon-pool/            模型 API 网关（候选）
│   ├── crawler-law/             旧法律数据采集（候选）
│   └── quiz-collector/          12 月后续题目与人工答题
├── reports/ScreenshotLegalBench_v2/ 报告和检索证据
├── hub_paths.py                副本跨项目路径解析
├── tools/                      迁移及文档工具
├── migration_manifest.json     复制范围与文件变更记录
├── verification.json           迁移时的哈希与语法核验
└── readme_verification.json    本次 README 文档核验
```

```mermaid
flowchart TD
    CN[中文判决 CSV] --> PARSE[主项目：解析与抽样]
    PARSE --> GEN[主项目：聊天生成]
    GEN --> SCORE[llm_evluator：质量评分与人工一致性]
    GEN -. 格式转换 .-> RENDER[llm_evluator：微信／WhatsApp 截图]
    UK[主项目：英国案例搜索] --> FULL[Batch：判决全文补抓]
    ANNO[人工截图标注] --> QA[主项目：属性展开]
    KIE[主项目：KIE 与消息框] --> IOU[IoU 匹配]
    QA --> IOU
    IOU --> QUESTIONS[评估问题]
    QUESTIONS -. 延续工作 .-> QUIZ[quiz-collector：题目与人工答题]
    LABEL[labelU-Kit 前端] -. 候选 .-> ANNO
    BACKEND[外部标注后端 :8000] --> LABEL
    POOL[silicon-pool 可选网关] -. 可配置调用 .-> GEN
```

实线表示已确认的代码／数据关联；虚线表示候选或需要转换的衔接。这些是独立脚本和服务，**无需一次启动全部项目**。

## 2. 按用途选择运行顺序

| 要做的工作 | 执行顺序 | 外部条件 |
| --- | --- | --- |
| 中文聊天生成 | 主项目抽样 → batch_infer_v2.py → llm_evluator 评分 | 模型配置与可用 API；评分需人工表 |
| 英国案例全文 | 主项目 uk_crawaler/main.py → detail.py → Batch/england_case_caller.py | 网络与案例网站 |
| 截图生成 | 准备 chatList JSON／WhatsApp JSONL → llm_evluator 截图脚本 | Playwright Chromium、生成页面 |
| 标注平台 | 准备外部标注后端 :8000 → LabelU 前端 :3004 | 该 Hub 没有标注后端 |
| 截图结构化评估 | 属性展开 → KIE 推理 → IoU 匹配 → 问题导出 v2 | 匹配的图片、标注版本和模型配置 |
| 人工答题与统计 | quiz-collector/generator.py → app.py :5000；另开 dashboard.py :5001 | 已有任务数据与图片 |
| 可选 API 网关 | silicon-pool → 手动配置调用方 base_url | API Key、网关认证配置 |

## 3. 环境和服务地址

Python 项目使用各自的 `.venv`；本文按 Windows PowerShell 和 Python 3.12 编写，需先安装对应解释器。LabelU 需要 Node.js 与兼容现有 v9 锁文件的 pnpm。模型推理、网站采集和人工 Web 服务的运行前提分别写在下方。

先在 PowerShell 定义 Hub 路径（如果移动目录，修改这一行）：

```powershell
$HubRoot = 'D:\\workspace\\screenshotLegalHub'
```

| 服务 | 地址 | 状态／依赖 |
| --- | --- | --- |
| 评分服务 | http://127.0.0.1:18321；/health、/docs | 模型与飞书配置 |
| LabelU 开发前端 | http://localhost:3004 | 外部标注后端 8000 |
| LabelU 静态预览 | http://localhost:3007 | 先构建，部署需后端路由 |
| API 网关：本地 Python | http://127.0.0.1:7898/v1 | 可选 |
| API 网关：Docker | http://localhost:17898/v1 | 可选，容器内部 7898 |
| 人工答题 | http://127.0.0.1:5000 | quiz-collector 数据 |
| 答题统计 | http://127.0.0.1:5001 | 同一 data 目录 |

下方每个项目都给出安装和启动命令。命令会在副本目录运行；模型调用、采集和评分会产生输出，评分工作流可能写回飞书。
'''
changed=[]
for idx,(name,(role,tree,description)) in enumerate(info.items(),4):
 d=P/name;guide=(d/guide_name).read_text(encoding='utf-8-sig').strip();body=guide.split('\n',1)[1].strip()
 # Keep all concrete startup commands, prerequisites, and existing limitations inline.
 root+=f'\n## {idx}. {name}\n\n{role}。{description}\n\n{tree}\n\n先进入项目目录：\n\n```powershell\nSet-Location (Join-Path $HubRoot "projects/{name}")\n```\n\n'
 root+=re.sub(r'^(#{2,6}) ',lambda m:'#'+m.group(1)+' ',body,flags=re.M)+'\n'
 readme=d/'README.md';upstream=d/'README.upstream.md';original=''
 if readme.exists():
  if not upstream.exists():shutil.copy2(readme,upstream)
  original=upstream.read_text(encoding='utf-8-sig')
 project_doc=f'# {name}\n\n## 项目架构\n\n{role}。{description}\n\n{tree}\n\n## 进入目录\n\n```powershell\nSet-Location "D:/workspace/screenshotLegalHub/projects/{name}"\n```\n\n'+body+'\n\n## Hub 中的位置\n\n[整体架构和其他项目命令](../../README.md) · [项目对应关系报告](../../reports/ScreenshotLegalBench_v2/项目对应关系说明.md)\n'
 if original:project_doc+='\n## 上游原说明\n\n原 README 保存在 [README.upstream.md](./README.upstream.md)。以下保留原项目介绍与原有命令；本 Hub 的入口以本文上方为准。\n\n'+original
 readme.write_text(project_doc,encoding='utf-8-sig');changed.append(readme.relative_to(H).as_posix())
root+='''
## 11. 报告、迁移范围和未完成的运行验证

- [项目对应关系报告](./reports/ScreenshotLegalBench_v2/项目对应关系说明.md)
- [工作区项目筛查](./reports/ScreenshotLegalBench_v2/工作区项目筛查.csv)
- [相关代码日期清单](./reports/ScreenshotLegalBench_v2/相关项目代码日期清单.csv)
- [迁移清单](./migration_manifest.json)、[迁移核验](./verification.json)、[路径审计](./path_audit.json)

代码、配置、已有数据和图片资源已复制。Git、node_modules、虚拟环境、缓存和构建目录没有复制；源目录中的这些内容仍然保留。代码中的已识别关联项目路径由 hub_paths.py 定位，历史数据内的原路径保留作为来源记录。

已有迁移核验覆盖 8,031 个源文件和副本的哈希、84 个 Python 文件语法；后续 README 编辑单独记录在 readme_verification.json。没有安装依赖或启动以上服务，因此这些命令是依据实际入口整理的启动说明，尚未做完整运行验收。

尚缺的输入包括 llm_evluator/datasets、主项目评分提示词 scoring_prompt_v3.md 与 v2_eval_modelrefine 问答表；LabelU 后端和爬虫数据库也需另行提供。Batch 通用历史脚本仍引用范围外 Spider_XHS 数据，详见路径审计；其英国案例流程已适配。

报告目录中的旧检索脚本属于历史归档，仍可能引用原工作区，不用作 Hub 的启动入口。
'''
backup=H/'README.before_startup_update.md'
if not backup.exists():shutil.copy2(H/'README.md',backup)
(H/'README.md').write_text(root,encoding='utf-8-sig');changed.append('README.md')
# Track documentation edits without claiming runtime validation.
m_path=H/'migration_manifest.json';manifest=json.loads(m_path.read_text(encoding='utf-8'));copied={e['destination'] for e in manifest['files']}
for rel in changed:
 if rel not in copied:continue
 entry=next((e for e in manifest['path_changes'] if e['file']==rel),None)
 if entry is None:entry={'file':rel};manifest['path_changes'].append(entry)
 entry['new_sha256']=hashlib.sha256((H/rel).read_bytes()).hexdigest();entry['change']='README expanded with Hub architecture and startup commands; upstream README retained'
manifest['readme_updates']=changed;m_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
# Verify README links, command blocks and their local script entrypoints.
errors=[];results=[]
for rel in changed:
 p=H/rel;txt=p.read_text(encoding='utf-8-sig');blocks=re.findall(r'```powershell\n(.*?)```',txt,re.S)
 if not blocks:errors.append({'file':rel,'error':'No startup command blocks'})
 if '项目架构' not in txt:errors.append({'file':rel,'error':'No architecture section'})
 for target in re.findall(r'\]\(([^)]+)\)',txt):
  if target.startswith(('https:','http:','#')):continue
  target=re.sub(r':\d+$','',target)
  if not (p.parent/target).exists():errors.append({'file':rel,'missing_link':target})
 results.append({'file':rel,'powershell_command_blocks':len(blocks),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
result={'readmes_updated':len(changed),'source_directories_modified':False,'architecture_and_commands_inline':True,'errors':errors,'files':results,'runtime_verified':False}
(H/'readme_verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False))
if errors:raise SystemExit(1)
