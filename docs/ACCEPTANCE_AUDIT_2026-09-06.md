# CLI_research × gpt_quant 验收审计

日期：2026-09-06；后续开发复验：2026-09-06

## 结论

离线研发交付通过；整体项目不应标记为“全部完成”或“实盘就绪”。

- `CLI_research`：研究、回测、Radar、跟踪、每日任务、跨仓验证入口通过离线验收。
- `gpt_quant`：验证闸门、v4 Paper 信号、正式交易日历、Agent 审计、治理签名和本地 Paper 执行桥通过离线验收。
- 仍未完成真实环境验收：真实模型 provider、SEC 数据授权与标注集、B0–B3 最终实验、至少 63 个真实 Paper 会话、券商 Paper/IBKR 连续运行。
- R4 实盘执行继续硬锁；研究结果最高只能进入 `PAPER_TRADING`。

## 可复现证据

基线：CLI `master@c8b4f4d`，GPT `main@0050d0d`。本轮未联网核验远端。

| 检查 | 结果 |
|---|---|
| CLI 正式测试集（排除历史 `* 2.py` 副本） | `130 passed` |
| GPT 测试集 | `121 tests OK` |
| `quant --help` / `gpt-quant --help` | 通过；无 editable 安装后的入口可运行 |
| CLI 合成研究演示 | 完成；明确标记为 synthetic、不可作为交易证据 |
| GPT Agent 演示 | 2 轮完成，10 个审计事件，JSONL 审计可落盘 |
| GPT Paper 演示 | 首次执行 1 笔；重启后重复信号拒绝；过期价格拒绝 |
| provider preflight | 缺凭据返回 `BLOCKED`，`network_called=false`，退出码 2 |
| 交易日边界 | 美股假日/提前收市拒绝；A 股午休拒绝；日历版本漂移有保护 |
| 代码编译 | CLI/GPT `compileall` 通过 |

正式测试命令：

```bash
cd /Users/brucehuang/Documents/CLI_research
.venv/bin/python -B -m pytest -q -p no:cacheprovider \
  $(find tests -maxdepth 1 -type f -name 'test_*.py' ! -name '* 2.py' | sort)
.venv/bin/python -B -m unittest discover -s ../gpt_quant/tests -q
```

## 本轮修复

- Paper JSON 信号拒绝 `bool`、字符串和非有限权重/参考价格。
- 直接 Paper 下单拒绝 `NaN`/`Inf`/非法价格，且失败不修改账户状态。
- A 股执行校验接入午休区间，不能只依赖交易所全天 session 边界。
- `agent-demo --audit-path` 现在真正写入 JSONL 审计，不再因参数签名不匹配崩溃。
- `gpt_quant` 的 `quant-contracts` 依赖改为可发布版本范围；本机绝对路径仅保留在 uv 本地源配置中。
- `CLI_research/uv.lock` 补齐共享 contracts 的锁定记录，修复安装后残缺 `quant` 包入口。
- M8-S4b 新增 `quant experiment-evaluate`：冻结 manifest、确定性实验 ID、B0–B3/N1–N2、成本压力、质量/容量门槛和 final-test 单次消费。

## 仍需单独验收

以下项目不能用本次离线测试替代：

1. 固定 provider/模型、预算、超时、真实 SEC 文档和人工标注集。
2. B0–B3 与负对照的完整最终测试，以及成本压力、容量、覆盖率和置信区间门槛。
3. 本地 Paper 连续运行、部分成交/断线/对账故障注入和至少 63 个真实交易会话。
4. IBKR Paper 账户身份、官方 API、恢复、通知和 close-only 订单链。
5. 目标发布环境的标准 PEP 517 wheel 构建与全新环境安装。本机本轮 `uv build` 受限于缺少缓存的 `hatchling/setuptools` 且 DNS 不可用；共享 `quant-contracts` 的无依赖 wheel 构建器已通过。

因此，本次验收状态为：核心离线模块 **OFFLINE_DONE**；M8-S4b 整体仍 **OFFLINE_PARTIAL**（SEC 增强 Radar、真实 LLM 特征和终测数据未完成），并且仍有 **EXTERNAL_VALIDATION_PENDING**，不是 `LIVE_READY`。
