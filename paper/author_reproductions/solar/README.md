# SOLAR — L05 / e04_symbolic_verifier

[作者论文](https://arxiv.org/abs/2509.00710) / [源码](https://github.com/albsadowski/solar/tree/067f8f78b128dc7647c8a54b2560a612fae91a87)。创新、原输入输出和适配边界见[Stage II入口头注](product_adapter.py)及[Stage I入口头注](stage_i_adapter.py)。独立Python3.13.14，49锁定依赖，无本地模型。

Stage II已实际执行固定SARA TBox和作者解释器，2次请求；原数值精确未命中、10%容差命中。该规则域不适用于中国聊天截图的责任判断或通用KIE/VQA。

本次补齐Stage I原图的审核前真实执行：完整作者SARA statute→概念与规则提取→整合→原validate_tbox→原human_review。新增4次API请求，首次3个date类型问题触发原整合修订，最终24类/71属性/21规则、原校验问题0。累计6/100；原模型换成已授权DeepSeek，所有请求和输出留存。

**仍部分完成**：目前在原作者人工审核输入处等待，没有自动approve。Stage I新解释器生成、训练样例反馈、中国产品规则域均未完成。原结构校验通过不是语义或法律准确率。

[具体审核包](STAGE_I_REVIEW_2026-10-30.md) · [完整I/O](../results/2026-10-29-per-paper/methods/solar/runs/c0d9a6be0adebf24__native_acquisition/solar.INPUT_OUTPUT.md) · [运行入口](run_stage_i.py) · [原任务记录索引](../results/2026-10-29-per-paper/README.md) · [环境](environment_state.json)。

执行差异：只替换结构化远程模型传输，串行化原图并发请求以共享父子协议；human_review调用原函数体，仅把实际input转为明确待审状态，没有替换TBox/训练答案或跳过批准。零付费协议测试确认未到code_generation。
