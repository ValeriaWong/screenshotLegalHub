# 源码提交与本地资产边界

本仓库提交源码、依赖与锁文件、配置模板、Schema、合成测试夹具和文档。本地案件材料与运行数据需要另行审核，不随源码更新上传。

## 排除的内容

- `.env` 及非 example 变体、`*.local.yaml`、本地模型配置、私钥、凭据文件；产品整个 `data` 目录包含数据库、用户原件、加密凭据主密钥。
- Python/Conda/Node 环境、模型权重、依赖缓存、构建输出、PM2/运行日志、测试临时目录。
- `datasets`、`projects`、历史快照、运行报告、原始模型响应、论文复现 runs/validation/results、下载的上游仓库及网页/论文存档。
- 工作区 `.agents`、`.codex` 配置，不作为产品源码发布。

`.gitignore` 不会自动取消已有跟踪。提交前必须同时检查实际索引及新增忽略规则；不删除本地材料，也不改写既有提交历史。历史文档中引用的报告和数据可能仅存在于完整本地工作区。

## 可重复的检查

```powershell
node tools/check_git_secrets.mjs --worktree
node tools/check_git_secrets.mjs --staged
node tools/check_git_secrets.test.mjs
git diff --cached --check
git diff --cached --stat
```

脚本仅依赖 Node 和 Git，工作区模式检查已跟踪及未忽略文件，索引模式读取全部已跟踪文件的 Git blob。检测已知 token 格式、私钥头、JWT、URL 凭据、字面量凭据和敏感路径，并在内存中与指定本地配置的凭据值比对；输出只包含位置和规则。读取失败会中止，不能被当作扫描通过。

已逐项核实的测试占位值以“文件、规则、完整行 SHA-256”记录精确例外，真实本地凭据比对不适用例外。两张 `product_v1/fixtures/demo_private_lending/chat-*.png` 是合成演示夹具，图片标题及 `fixture.json` 的 `synthetic` 标记说明其来源，已实际查看；其他二进制默认阻止提交，需要单独审阅。

扫描器自检在临时 Git 仓库内验证八个场景，包括工作区与索引分离、暂存后工作区覆盖、精确例外失效、本地凭据不能被例外绕过，以及未知二进制阻断；使用随机合成哨兵值，不调用真实供应商。

静态扫描无法保证识别所有敏感内容，也不能检查已忽略的原始材料。提交前仍需审阅差异、文件清单和模板；不要把密钥复制进文档或日志来证明扫描结果。
