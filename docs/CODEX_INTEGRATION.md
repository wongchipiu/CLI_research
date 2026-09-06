# Codex × CLI_research × gpt_quant：功能说明与落地需求

> 状态：架构与实施需求，2026-09-07。本文不表示任何模型、策略、Paper
> 或实盘能力已经验收。量化研究的当前事实仍以代码、`metrics.json` 和最新验收
> 记录为准。

## 1. 一句话结论

[`openai/codex`](https://github.com/openai/codex) 是可在本地工作区运行的开源编码
Agent 框架，提供项目指令、skills、受控工具、工作区权限、会话以及 SDK。它适合
帮助开发、测试和审阅量化系统；它不是回测、风控、券商或交易框架。

本项目采用以下职责分离：

```text
人类 + Codex（开发、审阅、受限的研究说明）
                 │ 仅传递已产生的摘要和结构化结论
                 ▼
CLI_research（唯一正式量化评价器） ──► 版本化研究证据 / 实验报告
                 │                            │
                 │                            ▼
                 └──────────────► gpt_quant（受限 LLM 特征、审计、PAPER_ONLY）
                                                   │
                                            无 R4 交易执行权限
```

**不可改变的规则：** Codex 的审批或 sandbox 只决定 Agent 是否能操作文件、命令和
网络，不能替代策略验证、风险判断、订单审批或人工交易授权。正式量化结论只能由
`CLI_research` 的确定性评价和 `gpt_quant` 的上下文绑定闸门产生。

## 2. 三个组件各自做什么

| 组件 | 已有/可用能力 | 应承担的职责 | 明确不承担的职责 |
|---|---|---|---|
| Codex | `AGENTS.md`、项目 skills、终端/文件工具、sandbox、会话、Python/TS SDK | 实现功能、审阅 diff、跑测试、解释已冻结证据、生成结构化研究备忘 | 回测打分、调参、风险放行、下单 |
| CLI_research | 数据质检、回测、训练/验证/最终测试隔离、实验 manifest/ledger、B0–B3/负对照 evaluator | 唯一正式策略与实验评价器；冻结和单次消费 final test | 让 LLM 替代确定性统计或重写历史结果 |
| gpt_quant | 引用绑定的文本特征、工具风险分级、审计、审批上下文、Paper 消费桥 | 从合格证据提取受限特征；校验并消费 `PAPER_ONLY` 信号 | 直接暴露券商密钥、R4 执行、宣布实盘准入 |

当前主线是 `M8-S4b`：在 CLI 的 B0–B3 对照实验中验证 LLM 特征是否带来独立、扣除
成本后的增量。这个问题必须由预登记的 manifest、数据快照、冻结参数、负对照和
最终测试回答；自然语言总结只用于解释结果。

## 3. Codex 能带来的功能

### 3.1 项目指令与 Skills：把正确流程变成默认行为

Codex 会读取工作区规则和 skills。`CLI_research/AGENTS.md` 已经规定“不读原始
行情/交易明细、只读摘要、一次对话一个 S 条目”；这正是量化 Agent 使用 Codex 的
第一道边界。现有 `research`、`backtest`、`review` skills 应继续保留为面向开发者和
研究者的快捷流程。

后续新增的 skills 必须只编排已存在的确定性命令，不能把交易逻辑写进 prompt：

| 建议 skill | 输入 | 允许动作 | 固定输出 | 禁止动作 |
|---|---|---|---|---|
| `quant-evidence-review` | 指定 `metrics.json`、manifest、实验报告 | 读取白名单中的小型 JSON/Markdown；验证 hash 和状态 | `ResearchMemoV1`：结论、证据、反证、局限、下一步 | 改参数、重跑/消费 final test、读行情或交易明细、下单 |
| `quant-regression-review` | 一项明确的 M8 变更 | 阅读最小代码范围，运行目标测试和契约反例 | 失败位置、风险级别、复现命令、未覆盖边界 | 更改生产证据、放宽阈值、吞掉失败 |
| `quant-provider-readiness` | provider 配置样例和 fixture | 检查密钥不落日志、超时/预算、schema 和引用校验 | readiness checklist 与缺口 | 用真实凭据测试、把外部文本当指令 |

每个 skill 都必须在 `SKILL.md` 写明：输入文件白名单、最大输入规模、允许的命令、
输出 schema、失败时的 fail-closed 行为，以及“不得产生订单或交易建议”。

### 3.2 受控开发与审阅

Codex 适合处理以下开发工作：

1. 为共享 contracts、市场日历、审批绑定、Paper 幂等和有限数值补反例测试。
2. 以独立审阅视角检查 PR/diff，重点找前视偏差、schema 不兼容、hash 漂移、越权
   工具、重放及异常恢复遗漏。
3. 在每次改动后运行局部测试；只有公共 contracts 变更才运行两仓完整回归。
4. 将确认过的决策和限制写回 `docs/`，而不是依赖长对话历史。

多 Agent 只适合并行且互不改同一文件的任务，例如“代码审阅”“测试设计”“文档对照”。
它们不能以多数投票决定策略、预测上涨概率或放宽准入；同一最终测试也不得被多个
Agent 反复消费。

### 3.3 可选的 SDK 旁路报告服务

Codex SDK 能以程序方式启动会话、接收流式事件并要求 JSON Schema 输出。它可在
**评价完成之后**生成说明性报告：

```text
manifest + evaluator JSON + metrics.json
       │
       ▼
只读 Codex report worker
       │  输出须符合 ResearchMemoV1
       ▼
docs/research/<date>-<topic>.md 或独立 report JSON
```

这项能力是 P3 可选项，不是 M8-S4b 的前置条件。worker 必须使用新会话或受限会话、
固定工作目录、显式环境白名单和 JSON Schema；它的输出不能回写 `metrics.json`、
experiment ledger、审批令牌或订单输入。

推荐 `ResearchMemoV1` 最小字段：

```json
{
  "schema_version": 1,
  "artifact_type": "research_memo",
  "task_id": "string",
  "evidence": [{"artifact": "path", "sha256": "hex", "claim": "string"}],
  "conclusion": "descriptive only",
  "counterevidence": ["string"],
  "limitations": ["string"],
  "next_steps": ["string"],
  "decision": "NO_TRADING_AUTHORITY"
}
```

`decision` 必须固定为 `NO_TRADING_AUTHORITY`。即使 evaluator 的研究结论为 PASS，
它也不能转化为 Paper 或实盘授权。

### 3.4 可选的窄 MCP/工具面

MCP 或自定义工具只能在受控 feature adapter 稳定后引入。第一版允许下列只读能力：

- `artifact.get_summary(path, sha256)`：只返回已验证的 `metrics.json` / report 摘要。
- `evidence.verify_citation(document_id, offsets, quote_hash)`：验证引用可定位且未漂移。
- `experiment.status(experiment_id)`：读取 manifest、trial 数和 final-test 是否已消费。
- `contracts.validate(payload)`：对输入运行共享 schema 与 canonical hash 检查。

第一版不得提供：任意 shell、任意 URL 抓取、原始行情读取、`broker.*`、订单写入、
密钥读取、调整策略阈值或重置 ledger 的工具。外部 SEC/行情数据仍由专门的 provider
adapter 获取、清洗和落盘；外部内容只是数据，不是 Agent 指令。

## 4. 日常使用方式

### A. 开发一个明确里程碑

1. 在相应仓库开始新会话，先读 `AGENTS.md`、`docs/REQUIREMENTS.md`、`docs/PLAN.md`
   和本条目的验收记录。
2. 用一句明确任务约束开始，例如：

   ```text
   实现 M8-S4b 的 <子项>。仅修改 <文件范围>；不得读取 data/、results/*.csv 或消费
   final test。先补反例测试，完成后运行 <目标测试命令> 并报告未验证边界。
   ```

3. 让 Codex 在当前仓库工作，不跨仓隐式导入源码；跨仓接口必须走共享 wheel 或公开
   CLI contract。
4. 人工审阅 diff 和测试结果。完成后更新对应验收记录/状态，再结束会话。

### B. 解读一次已有研究结果

1. 人工先确认 `metrics.json` 的 schema、`artifact_type`、数据/代码 hash、执行模型和
   `final_test_status`。
2. 只把该摘要、对应 manifest 和 evaluator report 交给 `quant-evidence-review`。
3. 报告必须先列证据与反证，再给出 `PASS` / `INCONCLUSIVE` / `BLOCKED` 的解释。
4. 任何“再试一个参数”“重跑最终集”“生成订单”的建议都停止，另建预登记研究任务。

### C. Provider 与 LLM 特征接入

1. 只由 `gpt_quant` 的受限抽取路径接触模型 provider；记录 model/provider 版本、
   prompt/template hash、输入证据 hash、运行 ID、输出 schema、调用成本和时间边界。
2. 输出的每个非 abstain 特征必须有引用偏移及 quote hash，并经本地证据校验。
3. CLI 将特征作为 B3 输入，与 B2 在同一时点股票池、价格、费用和交易规则下比较。
4. 先通过开发/验证阶段和负对照，再一次性消费 final test；样本不足或置信区间跨零即
   `INCONCLUSIVE`。

## 5. 落地需求与验收

### P0：立即保持的安全边界

| ID | 需求 | 验收标准 |
|---|---|---|
| C0-01 | CLI 是唯一正式评价器 | 任何 Agent/SDK 输出不被 evaluator 当作评分或准入输入 |
| C0-02 | gpt_quant 的 R4 持续硬锁 | `research`、`paper`、`live-confirm`、`live-limited` 都没有可用的真实提交工具 |
| C0-03 | 数据不进 Agent 上下文 | skills 不读取 `data/`、交易明细或大日志；脚本只产出受限摘要 |
| C0-04 | final test 单次消费 | manifest/ledger 反例覆盖重复消费、重跑和篡改 |
| C0-05 | 外部文本不可信 | provider/feature 入口对注入、超长内容、无引用、过期和超预算 fail closed |

### P1：完成真实模型接通前的工程缺口

| ID | 需求 | 建议落点 | 验收标准 |
|---|---|---|---|
| C1-01 | 实现或显式禁用真实 provider 的 tool-call 协议 | `gpt_quant.models.openai_compatible` | Provider 响应中的工具调用经 schema/ID/参数校验后才进入 executor；不支持时明确拒绝，绝不静默丢失 |
| C1-02 | 固定抽取运行身份 | feature / SEC evidence contract | 记录模型、prompt、provider、代码、证据与成本 hash；可从结果复现同一输入 |
| C1-03 | 端到端 B3 evaluator | CLI M8-S4b 主线 | B0–B3、N1/N2、成本压力、coverage、abstention、容量及统计区间全部生效 |
| C1-04 | 跨仓发布约束 | `quant-contracts` wheel 与 CI | 两仓锁定同一版本；golden fixture、坏 schema 和 hash 漂移都阻断 |

> C1-01 是当前最优先的具体缺口：`OpenAICompatibleGateway` 目前只解析文本和
> usage，尚未把 provider 的 `tool_calls` 变成 `ModelResponse.tool_calls`。在补齐前，
> 真实模型不能驱动既有通用工具循环；不要用 Scripted demo 的覆盖率推断真实路径可用。

### P2：把 Codex 变成可重复的开发/审阅工具

| ID | 需求 | 验收标准 |
|---|---|---|
| C2-01 | 新增 `quant-evidence-review` 与 `quant-regression-review` skills | 每个 skill 有输入白名单、命令白名单、最大输出、输出 schema、禁止动作和失败测试 |
| C2-02 | 最小权限 profile | Agent 看不到 `.env`、broker 凭据、原始数据和无关工作区；网络仅在明确 provider 验收时开放 |
| C2-03 | 审阅检查表 | PR/验收必须检查泄漏、final-test 单次消费、schema/hash、权限、恢复和可重现性 |
| C2-04 | 可追溯会话记录 | 记录 Codex 任务 ID、仓库 SHA、修改文件、测试命令和结果；不记录密钥或原始证据正文 |

### P3：可选的 SDK 与 MCP 产品化

只有 C0–C2、真实 provider 和 forward/Paper 验收完成后，才评估以下内容：

- 只读 Codex report worker，输出 `ResearchMemoV1`。
- 只读 artifact/evidence MCP，带身份、速率、审计和 schema 验证。
- 独立工作树的并行 review 任务，不共享写权限，不让子 Agent 修改实验 ledger。

每一项均需要 threat model、可观察性、失败回退和人工关闭开关；无已验证用户需求时，
不建设面向交易的 UI、通用 Agent marketplace 或自动化调度。

## 6. 权限、密钥和审计要求

1. Codex 进程的环境变量只保留运行需要的最小集合；broker 密钥、审批 HMAC secret 与
   provider 生产密钥不传给它。
2. 开发/审阅默认 `read-only` 或仅工作区写入；联网、安装依赖、访问外部 provider 都需
   明确任务和可审计授权。
3. 审计记录只存命令、版本、结构化结果、哈希和错误类别，不存 API key、完整 SEC 正文或
   不受限模型输出。
4. 失败一律向更低风险状态降级：无数据、超时、schema 不合格、引用失效、审批不匹配或
   对账异常都阻断新增风险。
5. 人工审批必须绑定具体 `OrderIntent`、风险报告、账户、策略批准、有效期与 nonce；
   Codex 输出不得参与签发或验证该审批。

## 7. 参考实现与文档入口

- Codex 仓库与 SDK：<https://github.com/openai/codex>；Python SDK：
  <https://github.com/openai/codex/tree/main/sdk/python>；TypeScript SDK：
  <https://github.com/openai/codex/tree/main/sdk/typescript>。
- 当前统一设计与 M8 路线：[LLM_TRADING_DESIGN.md](LLM_TRADING_DESIGN.md)。
- 当前执行顺序：[PLAN.md](PLAN.md)；实际已交付边界：[STATUS.md](STATUS.md)。
- CLI 唯一评价器和跨仓适配：[INTEGRATION_PLAN.md](INTEGRATION_PLAN.md)。
- GPT 的 Agent 运行时、工具风险与受限抽取：分别见相邻仓库的
  `src/gpt_quant/agent/runtime.py`、`tools/executor.py` 和 `feature_extraction.py`。

本文件回答“Codex 可以怎样帮助项目落地”。要了解策略是否通过、何时可进入 Paper 或
何时允许任何交易，必须回到 CLI evaluator、gpt_quant 审批链和相应的真实前向验收，
不能从本文件或任何 Agent 文字结论推导。
