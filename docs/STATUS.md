# 项目进度

> 每个 session 结束时更新本文件；新 session 开工先读这里。

## 已完成

- **M0 骨架**（2026-06-11）：uv + Python 3.12 环境、src 布局、pyproject（清华 PyPI 镜像）、git 仓库。
- **M1 数据层**（2026-06-11）：
  - 增量更新脚本 `scripts/update_data.py`，A股 5 只 + 沪深300 + 美股 5 只全部跑通（2024-01-01 起日线）。
  - 质量检查 `scripts/check_data.py` → `data/quality_summary.txt`，当前全部 [OK]。
  - 单测 5 个全过（storage 合并/去重逻辑）。

## 本机环境注意事项（重要，新 session 必读）

1. **代理**：本机挂 Clash（127.0.0.1:7890）。国内数据源必须绕过代理，`fetchers.py` 已在 import 时自动设置 NO_PROXY，勿删。
2. **数据源现状**：东财接口（stock_zh_a_hist / index_zh_a_hist）当前网络下连不通，运行时自动降级到新浪源；yfinance（Yahoo）同样不可用，自动降级新浪美股源。**新浪源是当前唯一稳定源**。
3. **新浪源量纲**：volume 单位是股（东财是手）；做成交量因子时注意。
4. uv 装在 winget 路径，老 shell 可能不在 PATH；新开终端可直接用 `uv`。
5. Windows 控制台 GBK：脚本已内置 `sys.stdout.reconfigure(encoding="utf-8")`。

- **M2 回测引擎**（2026-06-12）：组合级日频引擎（决策 t 收盘执行赚 t+1 收益）、
  涨跌停/停牌约束、费用模型、绩效指标、metrics.json + nav.png 落盘。21 个单测全过。
- **M3 基线策略**（2026-06-12）：sma_cross / momentum / boll_revert，注册表接口。
  6 组回测（2018~2026）已跑通：美股 momentum 最佳（cagr 30.3%, sharpe 1.04，超额 16%/年）；
  A股 momentum 超额 9%/年；boll_revert 两市场均跑输基准。
- **M4 Agent 层**（2026-06-12）：/research、/backtest、/review 三个 skills + CLAUDE.md 约定。

## 下一步：M5 投入使用

- 日常：/research 提想法 → 写新策略到 strategies/ → /backtest 验证 → /review 复盘。
- 候选改进：动量参数敏感性（lookback 60/120/250）、A股池扩到沪深300成分、波动率目标仓位。

## M5 策略研究记录

- **A股热点小盘股尾盘隔夜动量**（2026-08-30）：已建立独立研究目录，完成逻辑审查、可证伪假设、分钟级忠实回测规范、日线近似方案、风险边界和参考资料卡片。当前引擎只能做日线近似；忠实验证需要分钟行情、自由流通市值/换手率、板块成分与交易事件数据。

## 待办/技术债

- 数据已补全 2018-01-02 起。混源情况：东财间歇可用，部分标的东财、部分新浪，
  **volume 量纲不一致（手 vs 股）**，做量价因子前需统一。
- cn-index 的东财失败 warn 每次都会打印一次，属预期噪音。
- 扫参数（grid search）应做成确定性脚本，勿让 agent 循环跑回测烧 token。
