# Skills

统一接口为 async LegalSkill.run(SkillContext, SkillInput) → SkillResult。内置 manifest 位于 `plugins/skills/manifests/`，实现位于 `deterministic.py`。13 项能力覆盖 perception、route、timeline、claim、fact、burden、map、strength、gap、contradiction、strategy、adversarial、verification。

Resolver 固定优先级：显式 run override → matter-specific → jurisdiction/practice-area → generic。同级多候选产生 CompileError，不使用最后注册覆盖。Profile 在 `profiles/cn_civil_default.yaml`，capabilities 可配置 capability → skill ID；显式 overrides 优先于 profile。

Manifest 声明适用范围、输入 selectors、输出 kinds、依赖、stage、grounding、trust 和六项 permissions。Runtime 再次授权，校验已编译 digest 与输出类型、来源 IDs；Application Services 统一写数据库。Skill 不操作 API/UI/Pack、不直接 commit。

v1 内置确定性实现属于可复现的规则线索分析：关键词映射不会自动判定款项性质或金额；同一 Fact 同时出现支持/反证时标为 mixed，缺少银行原件仍生成补证项。策略只引用已形成的图结构。专业生产 Skill 可以替换接口实现，但应补充 grounding 和领域评测。

当前没有动态 import 任意第三方 Python 的入口；第三方执行器接入应先经信任配置和代码审查，再注册实现工厂。不能把 Manifest 当成 OS 沙箱。
