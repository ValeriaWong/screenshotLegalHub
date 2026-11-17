可以，而且我觉得 MinerU 对你这个项目有一个很值得借鉴的点：**不是“拿 MinerU 替换你的 ScreenshotLegal”，而是把它理解成一个成熟的 Evidence Document Runtime。**

我把 MinerU 4.x 的当前代码和设计文档看了一遍。结论先说：

> **MinerU 很适合成为 ScreenshotLegal 的“通用文档证据解析层/参考架构”，尤其值得借它的统一中间表示、文档缓存、渐进式读取、稳定 locator 和原文回溯。**
>
> **但它不适合直接替换你的微信截图结构化，也不做请求权、待证事实、举证责任、证据证明力、Proof Matrix。**

而且目前有几个项目各自在某个方面甚至比 MinerU 更适合你：**Docling、PaddleOCR/PP-StructureV3、RAGFlow/DeepDoc、Marker**。我最终会建议你做 adapter architecture，而不是赌一个 parser。

---

# 一、先把 MinerU 的宣传拆开看

MinerU 4.0 现在宣传的是：

> 多格式解析 + 本地文档库 + Agent 阅读 + 稳定引用位置。

支持 PDF、图片、DOC/DOCX、PPT/PPTX、XLS/XLSX、RTF、OpenDocument、EPUB、OFD、HTML/MHTML、CSV/TSV；PDF/图片可以使用不同质量 tier，Office 等原生文档走本地解析，并统一输出为结构化文档模型。[GitHub](https://github.com/opendatalab/MinerU/blob/master/docs/en/index.md?utm_source=chatgpt.com)

但是这里有一个特别重要的概念：

### “长文档渐进式分析”其实主要是“渐进式读取”

不是：

```text
300页判决
↓
MinerU自动理解全部案件
↓
自动形成法律结论
```

而是：

```text
300页判决
↓
解析、结构化、缓存
↓
给每个 page/block 稳定地址
↓
Agent 先读取有限范围
↓
如果没读完
返回 next_request
↓
继续从精确位置读取
```

MinerU 自己也明确把产品定位为 Agent 的 document reader，而不是 RAG framework、vector database 或 chat-with-doc 应用。[PyPI](https://pypi.org/project/mineru/4.0.0/?utm_source=chatgpt.com)

这个区别对你特别重要。

---

# 二、代码级看 MinerU 到底是怎么做的

我把核心调用链压缩成下面这张图：

```text
                    MinerU 4.x

                  原始文件
                     │
                     ▼
              MinerUParser
                     │
         根据 file suffix 路由
                     │
       ┌─────────────┼──────────────┐
       ▼             ▼              ▼
      PDF          Office         HTML/EPUB...
       │
       ▼
   doc_analyze()
       │
       ▼
format-specific analyzer
       │
       ▼
     ModelJson
       │
    postprocess
       ▼
    MiddleJson
       │
       ├───────────────┬───────────────┐
       ▼               ▼               ▼
   Markdown      StructuredContent   ContentList
       │
       ▼
      Doclib
       │
       ├─ SHA256 identity
       ├─ cache
       ├─ FTS search
       ├─ tier/version
       └─ locator
              │
              ▼
          Agent Read
              │
        page / block / char
              │
              ▼
        next_request
```

这是 MinerU 真正值得你研究的部分。

---

# 三、多格式不是“全部先 OCR”，而是不同 parser 最后收敛成一个模型

MinerU 当前 `MinerUParser` 的思路大致是：

```python
if pdf:
    analyze_pdf(...)
elif csv:
    analyze_csv(...)
elif epub:
    analyze_epub(...)
elif html:
    analyze_html(...)
elif ofd:
    analyze_ofd(...)
else:
    analyze_office(...)
```

图片输入则先转换到 PDF 路径，再进入 PDF 分析。

最终不管来源是什么，都会走向：

```text
ModelJson
↓
MiddleJson
```

而目前统一的核心文档结构可以理解成：

```text
MiddleJson
└── pages[]
    └── blocks[]
        └── inline content / spans
```

MinerU 4.0 官方也明确把它描述为一个 shared document model，再由 renderer 输出 Markdown、HTML、DOCX、PDF、Structured Content、Content List 等不同形式。[GitHub](https://github.com/opendatalab/MinerU/blob/master/docs/en/reference/output_files.md?utm_source=chatgpt.com)

## 这和我们给 ScreenshotLegal 设计的架构其实非常像

MinerU：

```text
PDF
DOCX
PPTX
Image
HTML
   ↓
MiddleJson
   ↓
different renderers
```

你的系统：

```text
微信截图
PDF
合同
银行流水
Email
   ↓
Evidence Core
   ↓
ProofGraph
   ↓
Timeline / Proof Matrix / Strategy / Review
```

所以这里我认为 MinerU 的**架构思想非常值得借**。

但：

> 不要直接把 `MiddleJson` 当成 ScreenshotLegal 的核心 Schema。

后面我解释为什么。

---

# 四、MinerU 所谓长文档，其实有“两层切分”

这是我觉得很聪明的地方。

## 第一层：解析时防止大文档把显存/内存炸掉

MinerU 的 PDF pipeline 不是几百页同时跑。

源码中有：

```text
mineru/backend/analysis/pdf/window.py
```

它建立：

```text
ProcessingWindow
```

把 PDF 拆成页面窗口处理。

当前源码默认窗口配置入口是：

```text
MINERU_PROCESSING_WINDOW_SIZE
```

官方文档也明确把它定义成 large-document processing window，用于控制大文档解析过程的内存与吞吐。[OpenDataLab](https://opendatalab.github.io/MinerU/zh/usage/cli_tools/?utm_source=chatgpt.com)

因此：

```text
500页 PDF

1-64
65-128
129-192
...
```

这样的处理思想，本质上是：

> **Bounded parsing context**

而不是把整个文件一次送进模型。

---

# 五、第二层才是给 Agent 的“渐进式阅读”

这是另一套机制。

解析完成以后：

> 不代表 Agent 每次就要读取整篇 Markdown。

MinerU 专门设计了：

```text
DocContentResponse
```

核心字段：

```python
sha256
short_id
tier

content

request_scope
content_ranges

truncated
next_request
```

默认：

```text
limit = 30000 characters
```

分页文档默认：

```text
page_range = 1-10
```

如果没有读完：

```json
{
  "truncated": true,
  "next_request": {
    "page_range": "7-10",
    "after": "doc:abc/tier:basic/page:7/block:4"
  }
}
```

如果这 10 页读完了，但是文档还有后面：

```json
{
  "truncated": false,
  "next_request": {
    "page_range": "11-20"
  }
}
```

这个协议是 MinerU 4.x 明确设计出来的，而不是简单字符串截断。[MinerU](https://mineru.atomgit.com/next/decisions/0013-doc-content-progressive-reading.html?utm_source=chatgpt.com)

这对你的 Agent Runtime 很值得借鉴。

---

# 六、真正关键的是 locator

MinerU 当前 locator 是这种东西：

```text
doc:ab12cd3
/tier:basic
/page:7
/block:4
/char:32784
```

也就是：

```text
Document
↓
Tier
↓
Page
↓
Block
↓
Character Offset
```

Agent 得到一句内容以后，不只是：

```text
“被告于3月10日确认债务”
```

而是可以同时知道：

```text
doc:abcdef
/tier:standard
/page:82
/block:17
```

以后再调用：

```text
mineru read <locator>
```

直接回这个地方。

甚至能够：

```text
--context 2
```

把前后上下文一起读出来。MinerU 的设计明确要求 `read(locator)` 从已经缓存的结构化解析结果读取，而不是每次重新 parse 文件。[MinerU](https://mineru.atomgit.com/next/decisions/0014-mineru-read-command.html?utm_source=chatgpt.com)

---

# 七、这其实就是我们之前给 ScreenshotLegal 设计的 SourceRef

你现在设计的是：

```json
{
  "image_id": "img12",
  "message_id": "m31",
  "bbox": [x1,y1,x2,y2],
  "quote": "月底之前把5万给你"
}
```

MinerU 是：

```text
doc
page
block
char
bbox
```

两者实际上是同一种设计哲学：

> **模型的结论不能只保存文本，必须保存“回到原材料的位置”。**

所以我建议把你现在的 SourceRef 再升级一点：

```text
SourceRef

evidence_id
source_sha256

source_type

page_no
block_id

image_id
message_id

bbox
quote

parser_name
parser_version
parse_run_id

source_locator
```

例如 PDF：

```json
{
  "evidence_id": "e001",
  "source_sha256": "...",
  "page_no": 82,
  "block_id": "17",
  "bbox": [0.12,0.31,0.76,0.42],
  "quote": "……",
  "parser_name": "mineru",
  "source_locator":
    "doc:abc/tier:standard/page:82/block:17"
}
```

微信：

```json
{
  "evidence_id": "e002",
  "image_id": "img12",
  "message_id": "m31",
  "bbox": [634,811,1010,942],
  "quote": "月底之前把5万给你",
  "parser_name": "wechat_structure"
}
```

这样所有 Evidence 都统一。

---

# 八、MinerU 的本地文档库其实也值得你借

它不是 parse 完扔个 Markdown 文件。

4.x 有：

```text
Doclib
```

负责：

```text
file discovery
SHA256
cache
parse records
tier
search index
continuation
locator
```

官方现在把：

> discover files → cache → search → page/block continuation → stable citation

作为文档库核心工作流。[GitHub](https://github.com/opendatalab/MinerU/blob/master/docs/en/index.md?utm_source=chatgpt.com)

代码里检索实现并不是 LLM 搜索，而是本地全文索引。

这和你之前决定：

> 案件内部 retrieval 用代码做，不让模型自己搜。

方向完全一致。

---

# 九、所以 MinerU 放到你的项目里，应该在哪一层？

我建议：

```text
                       ScreenshotLegal

                    Evidence Router
                          │
       ┌──────────────────┼─────────────────────┐
       │                  │                     │
       ▼                  ▼                     ▼
 WeChat Screenshot     PDF/Scan            DOCX/PPTX/XLSX
       │                  │                     │
       ▼                  ▼                     ▼
WeChatStructure     DocumentParser        DocumentParser
   Adapter              Adapter               Adapter
       │                  │                     │
       │           ┌──────┼──────┐              │
       │           ▼      ▼      ▼              │
       │        MinerU  Docling Paddle           │
       │                  │                     │
       └──────────────────┼─────────────────────┘
                          ▼
                 Canonical Evidence Core
                          │
                          ▼
                      SourceRef
                          │
                          ▼
                         Event
                          │
                          ▼
                   Fact Proposition
                          │
                          ▼
                    Legal Element
                          │
                          ▼
                        Claim
```

也就是说：

# MinerU 应该是 Adapter

不是 ScreenshotLegal Schema。

---

# 十、那 MinerU 对你的各种材料到底适配得怎么样？

这里必须区分：

> **架构适配程度**

和：

> **我已经在你的真实数据上测出的准确率**

现在我能判断前者，但这轮还没有拿你的真实材料跑 MinerU，所以我不会声称“准确率很好”。

我会这样预估：

| 你的证据类型 | MinerU 适配 | 原因 |
|---|---:|---|
| 电子版法院判决 PDF | ★★★★★ | 非常典型的文档解析场景 |
| 扫描判决书 | ★★★★☆ | OCR + layout 很适合，需要实测中文扫描质量 |
| 合同 PDF | ★★★★☆ | 标题、段落、表格、版面定位合适 |
| Word 合同/文书 | ★★★★★ | 4.x 已支持原生文档路径 |
| Excel 银行流水 | ★★★★☆ | 多格式 ingest 强，但法律表格准确度需专测 |
| 扫描银行流水 | ★★★☆☆ | 表格 OCR 难度高，应与 Paddle 比 |
| 论文/研究报告 | ★★★★★ | 本来就是它重点场景 |
| 普通照片证据 | ★★★☆☆ | 可以解析，但不等于取证语义理解 |
| 微信聊天截图 | **★★☆☆☆** | 最大短板 |
| 多张连续微信截图 | **★★☆☆☆** | 不懂跨图 message identity/会话连续性 |
| 请求权分析 | ☆☆☆☆☆ | 不是 MinerU 的职责 |
| 举证责任 | ☆☆☆☆☆ | 不是它的职责 |
| Proof Matrix | ☆☆☆☆☆ | 需要你的法律系统 |
| 法律策略 | ☆☆☆☆☆ | 需要你的 Skills/Agents |

---

# 十一、为什么微信截图我不建议直接交给 MinerU

MinerU 会看到：

```text
图片
↓
layout
OCR
blocks
```

但是你的微信截图真正需要的是：

```text
谁说的
↓
哪一个聊天气泡
↓
消息边界
↓
左右双方
↓
时间戳属于哪条消息
↓
头像/昵称
↓
图片消息/转账消息
↓
撤回
↓
前后截图是否重复
↓
多张截图是不是同一会话
```

例如：

```text
        张三
  ┌─────────────┐
  │ 月底一定还你 │
  └─────────────┘

          vs

                   李四
             ┌──────────┐
             │ 我没借过 │
             └──────────┘
```

普通 document parser 可能很好地 OCR 出：

```text
月底一定还你
我没借过
```

但真正法律上重要的是：

```text
speaker A
    → promise

speaker B
    → denial
```

所以：

> **OCR 正确 ≠ 证据结构正确。**

这也是你 ScreenshotLegalBench 最值得做的地方。

---

# 十二、除了 MinerU，我认为你最应该看的其实是 Docling

如果问：

> “哪个项目的 Schema 思想最适合我们现在 ScreenshotLegal 架构？”

我反而会说：

# Docling

Docling v2 有统一的：

```text
DoclingDocument
```

它可以表达：

```text
Text
Table
Picture
Hierarchy
Section
Header/Footer
Layout
Provenance
```

而且每个文档元素都有 `ProvenanceItem`：

```text
bbox
charspan
page_no
```

这跟你现在的 `SourceRef` 非常契合。[Docling Project](https://docling-project.github.io/docling/reference/docling_document/?utm_source=chatgpt.com)

更值得你看的还有：

# Docling Graph

它专门做：

```text
document
↓
structured chunks
↓
entity / graph
↓
provenance ledger
```

它的 graph node 可以确定性地回到：

```text
chunk
page
character span
```

而且 provenance bookkeeping 本身不依赖 LLM。[Docling Project](https://docling-project.github.io/docling-graph/fundamentals/graph-management/provenance/?utm_source=chatgpt.com)

这和你的：

```text
Fact Proposition
↓
EvidenceLink
↓
SourceRef
```

几乎是同一个研究问题。

只是你这里多了一层：

```text
Legal Element
Claim
Burden
```

---

# 十三、对中文扫描法律材料，我会重点测 PaddleOCR PP-StructureV3

PP-StructureV3 更像：

> 文档 perception engine。

它现在重点支持：

```text
layout detection
OCR
table
formula
chart
reading order
Markdown
JSON
```

而且 layout 模型明确包含合同、论文、研报等中英文文档类型。[GitHub](https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/algorithm/PP-StructureV3/PP-StructureV3.md?utm_source=chatgpt.com)

它甚至输出不同模块的可视化/结构结果：

```text
layout_det_res
overall_ocr_res
text_paragraphs
formula
table
seal
```

等。[GitHub](https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/pipeline_usage/PP-StructureV3.en.md?utm_source=chatgpt.com)

所以对你：

```text
中文判决扫描件
合同
银行流水
盖章文件
```

PP-StructureV3 很有竞争力。

但它没有 MinerU 那么完整的：

```text
doc library
stable locator
progressive Agent reading
```

所以属于：

> **解析后端候选**

而不是完整 Evidence Runtime。

---

# 十四、Marker 也非常值得作为 benchmark

Marker 现在的架构也很干净：

```text
Provider
↓
Builder
↓
Processors
↓
Schema
↓
Renderer
↓
Converter
```

它会根据页面情况决定：

```text
直接取 PDF text
还是 OCR
还是 VLM
```

而不是所有页都跑大模型。[GitHub](https://github.com/datalab-to/marker/blob/master/README.md?plain=1\&utm_source=chatgpt.com)

JSON 是真正的 block tree：

```text
Page
├── SectionHeader
├── Text
├── Table
├── Figure
└── ...
```

每个 block 有：

```text
id
block_type
polygon
children
section hierarchy
``` :chatgpt-content-reference{index="12"}


所以它特别适合用来测试：

> **换 parser 到底会不会改善下游法律分析。**

但是 Marker 没有 MinerU 那套成熟的 document library + locator continuation，所以如果做产品底座，我不会优先于 MinerU/Docling。

---

# 十五、RAGFlow / DeepDoc 是另一个方向

RAGFlow 更像一个完整产品平台：

```text
parse
↓
chunk
↓
index
↓
retrieve
↓
RAG/agent
```

而且一个很有意思的地方是，它现在自己就把 parser 做成可切换的。

PDF parser 可以选择：

```text
DeepDoc
MinerU
Docling
PaddleOCR
...
``` :chatgpt-content-reference{index="13"}


这实际上证明了我们之前给 ScreenshotLegal 定的：

> `DocumentParserAdapter`

这个架构方向是对的。

DeepDoc 自己则支持 OCR、layout、table structure，PDF 输出保留 page + rectangle positions。:chatgpt-content-reference{index="14"}

但整个 RAGFlow 对你来说太重。

因为你自己已经准备做：

```text
Evidence Core
Retrieval
Matter Pack
Skills
ProofGraph
Review
```

再把 RAGFlow 整套嵌进来，很容易形成两个 runtime。

---

# 十六、我现在给这几个项目的定位

| 项目 | 我认为最值得你借的东西 | 是否适合直接作为底座 |
|---|---|---:|
| **MinerU** | Document Library、渐进读取、locator、缓存、多格式解析 | **很适合做文档层参考/Adapter** |
| **Docling** | 统一 typed document schema、provenance、hierarchy | **非常适合 Evidence Schema 参考** |
| **Docling Graph** | Graph → source deterministic provenance | **非常适合 ProofGraph 参考** |
| **PP-StructureV3** | 中文 OCR、版面、表格、公式、印章 | **最适合 perception backend** |
| **Marker** | PDF conversion pipeline、block tree、选择性 OCR/VLM | **强 benchmark/backend** |
| **DeepDoc** | OCR/layout/table + page rectangle | backend 候选 |
| **RAGFlow** | parser adapter、chunk/index/retrieval 平台 | 更适合参考，不建议整套嵌入 |
| **你的 WeChat parser** | speaker/message/timestamp/cross-image | **微信证据仍应作为主路线** |

---

# 十七、如果是我现在改 ScreenshotLegal 架构，我会这么做

而不是：

```text
ScreenshotLegal
↓
MinerU
↓
everything
```

我会变成：

```text
                EvidenceIngestionPort

                       │
        ┌──────────────┼──────────────────────┐
        │              │                      │
        ▼              ▼                      ▼
ChatScreenshot      Document               Raw Media
        │              │                      │
        ▼              ▼                      ▼
WeChatAdapter    DocumentAdapter         VisionAdapter
                       │
             ┌─────────┼───────────┐
             ▼         ▼           ▼
          Docling    MinerU      Paddle
                        │
                     Marker
                 benchmark only
                       │
        └──────────────┼──────────────────────┘
                       ▼
                EvidenceDocument
                       │
                       ▼
                   SourceRef
                       │
                       ▼
                 Evidence Core
                       │
             ┌─────────┴────────┐
             ▼                  ▼
         Retrieval           Timeline
             │
             └─────────┬────────┘
                       ▼
                Fact Proposition
                       ▼
                 Legal Element
                       ▼
                     Claim
                       ▼
                 Proof Matrix
```

这里 MinerU、Docling、Paddle 都只是：

```python
class DocumentParserAdapter:
    def parse(...) -> EvidenceDocument:
        ...
```

---

# 十八、我会新增一个你之前架构里还缺的对象：`EvidenceDocument`

类似：

```python
EvidenceDocument
    evidence_id
    sha256
    mime_type

    parser:
        name
        version
        profile
        run_id

    pages:
        Page[]

Page
    page_no
    width
    height

    blocks:
        DocumentBlock[]

DocumentBlock
    block_id
    block_type

    text

    bbox
    reading_order

    parent_id
    children

    source_anchor
```

这样：

MinerU：

```text
MiddleJson
↓ adapter
EvidenceDocument
```

Docling：

```text
DoclingDocument
↓ adapter
EvidenceDocument
```

Paddle：

```text
PPStructure JSON
↓ adapter
EvidenceDocument
```

Marker：

```text
Marker block tree
↓ adapter
EvidenceDocument
```

都可以比较。

---

# 十九、而微信截图不要强行塞成 DocumentBlock

这是另外一个重要判断。

微信应继续保留：

```text
Conversation
Message
Speaker
Timestamp
SourceRef
```

而不是：

```text
Page
Block
Block
Block
```

最后统一的位置应该是：

```text
Evidence Core
```

而不是 parser schema。

因此：

```text
Document evidence
→ EvidenceDocument
→ Event

Chat evidence
→ Conversation/Message
→ Event
```

从：

```text
Event / Fact
```

开始汇合。

这个设计会干净很多。

---

# 二十、到底选 MinerU 还是 Docling？

如果只能让我现在先选一个作为**产品默认通用文档 parser**，我会偏：

> **Docling 作为默认 Schema-oriented parser，MinerU 作为重要 backend + long-document reference implementation。**

原因不是说 Docling OCR 一定比 MinerU 好。

而是你的产品最重视：

```text
source grounding
provenance
typed schema
ProofGraph
```

Docling 的 `ProvenanceItem(page_no, bbox, charspan)` 和 `DoclingDocument` 很贴这个方向。[Docling Project](https://docling-project.github.io/docling/reference/docling_document/?utm_source=chatgpt.com)

但如果你的目标变成：

> 大量几百页卷宗，让 Agent 局部读取、继续读取、不要每次重解析、必须稳定引用。

那么：

> **MinerU 的 doclib + locator + continuation 设计比 Docling 更值得直接借。**

所以我实际上最推荐的是：

# “Docling 的 Schema + MinerU 的 Doclib/Locator 思想”

再加：

# “Paddle 的中文 perception”

而不是三选一。

---

# 二十一、最重要的是：别根据 README 决定谁效果好

对你而言真正要测的是：

| Metric | 为什么重要 |
|---|---|
| OCR CER | 基础文字正确 |
| Block Recall | 有没有漏掉证据 |
| Reading Order | 判决、合同顺序 |
| Table Structure | 银行流水 |
| Page Accuracy | Citation 页面正确 |
| BBox IoU | 原文高亮正确 |
| Quote Exact Match | 引文是否真来自证据 |
| Speaker F1 | 微信专用 |
| Message Segmentation F1 | 微信专用 |
| Timestamp Assignment | 微信专用 |
| Citation Precision | 法律结论引用是否真的支持 |
| Citation Recall | 是否遗漏关键证据 |
| Downstream Claim Accuracy | parser 最后有没有真正帮助法律分析 |
| Evidence Mapping F1 | 证据是否映射到正确待证事实 |

最后一组反而最重要。

因为完全有可能出现：

```text
Parser A OCR = 98%
Parser B OCR = 96%

但是

A → Claim Accuracy = 72%
B → Claim Accuracy = 81%
```

那对 ScreenshotLegal 来说：

> B 才是更好的 parser。

---

# 二十二、所以这跟你之前的 Benchmark 设计正好接上

我们之前说：

```text
Raw Image
Image + OCR
Image + OCR+bbox
Structured Message
```

现在可以扩成：

```text
Generic Document Track

D0 raw multimodal model
D1 MinerU
D2 Docling
D3 Paddle PP-Structure
D4 Marker

Chat Track

C0 raw multimodal
C1 generic OCR
C2 MinerU
C3 Paddle
C4 WeChatStructure
```

然后固定同一个：

```text
Fact Skill
Evidence Mapping Skill
Claim Skill
```

只换 parser。

这样你才能科学回答：

> MinerU 到底对 ScreenshotLegal 有没有帮助？

而不是：

> MinerU 看起来功能很多，所以我们用 MinerU。

---

## 最终建议

**MinerU 值得接，而且非常值得研究源码，但我不会把它做成 ScreenshotLegal 的核心依赖。**

我会从 MinerU 直接借鉴三件架构思想：

```text
统一中间文档表示
+
SHA/cache/document library
+
稳定 page/block locator + progressive read
```

具体 parser 则保持可替换。

当前我会把候选组合定为：

> **微信截图：你自己的 WeChatStructureAdapter**
>
> **普通结构化文档：Docling**
>
> **长 PDF / Agent 渐进阅读：MinerU**
>
> **中文扫描件/表格：PP-StructureV3**
>
> **PDF conversion benchmark：Marker**
>
> **RAGFlow/DeepDoc：作为平台/adapter 架构参考和额外 baseline**

最关键的一点是：**MinerU 解决的是“怎么把证据可靠地变成机器可读、可续读、可定位的数据”，你的 ScreenshotLegal 解决的是“这些证据法律上证明什么”。这两个层次正好可以拼起来，但不应该合并。** [GitHub](https://github.com/opendatalab/MinerU/blob/master/docs/en/index.md?utm_source=chatgpt.com)