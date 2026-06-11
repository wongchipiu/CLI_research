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

## 下一步：M2 回测引擎

- S1：pandas 向量化回测核心 + 费用/滑点模型（先写 200 行内设计概要确认再实现）。
- S2：A股 T+1、涨跌停约束（必须带单元测试）。
- S3：绩效指标 + 基准对比 + metrics.json 落盘。

## 待办/技术债

- 起始日期目前用 2024-01-01（验证用）；正式研究前把历史拉到 2018-01-01（删掉 data/ 重拉或直接再跑一次 --start 2018-01-01 即可，增量合并会处理）。
  注意：新浪 qfq 全量返回，重拉成本低；东财恢复后两源复权因子可能有差异，同一标的尽量保持单一来源。
- cn-index 的东财失败 warn 每次都会打印一次，属预期噪音。
