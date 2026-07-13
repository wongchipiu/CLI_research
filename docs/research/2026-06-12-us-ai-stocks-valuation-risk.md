# 美股 AI 股走势与估值风险（算力 / 存储 / 光模块）

> 日期：2026-06-12 | 方法：/research 调研笔记 | 数据截至 2026-06-12
> 免责：信息与逻辑整理，非投资建议。

## 结论先行

1. **三大环节仍在景气兑现期，基本面是真的**：算力（NVDA/AVGO/MRVL）、存储（MU，HBM 售罄）、光模块（AAOI/COHR/LITE）2026 上半年业绩与指引普遍 beat-and-raise，由超大厂 capex（2026 全球 AI 支出约 6700 亿美元）驱动。
2. **但估值与"循环融资"是核心风险**：S&P500 前五大公司占指数 30%（半世纪最高集中度）；Goldman 称约 19 万亿美元市值跑在经济影响之前。NVDA↔OpenAI↔Oracle↔CoreWeave 的循环交易（Nvidia 投 OpenAI 1000 亿、Stargate 3000 亿）使同一笔钱在少数公司间循环、互相做高收入——**需求一旦不及预期，闭环会快速反向解体**。
3. **对稳健投资者**：不是"清仓避险"，而是"分层"——核心仓握有自由现金流、客户多元的卖铲人（TSM、AVGO、MU 龙头），对纯弹性/亏损叙事股（如部分光模块）严控仓位与止盈纪律。判断信号见"可证伪假设"。

## 三环节现状

**算力**
- NVDA：FY27 Q1（截至 2026-04-26）营收 816 亿、+85%；数据中心 752 亿、+92%（Blackwell 300 放量）；季度股息提至 0.25 美元。
- MRVL：FY27 Q1 营收 24.18 亿、+28% 创纪录，"AI 订单异常强劲"，上调 FY27/FY28 指引；Wells Fargo 看 FY29 定制 XPU >100 亿美元。custom ASIC + 光互连双轮。
- AVGO（博通）：6/3 财报为"AI 需求是否仍加速"的关键信号；网络 + 定制硅龙头。

**存储**
- MU：2026 涨约 70%，近 52 周高约 546 美元；**HBM 全年售罄、未来数季在手合约锁定**；6/24 财报是关键。GS 目标价上调至 900。DRAM/NAND 价格紧、AI 可见度高。

**光模块**
- AAOI：2026 涨约 439%，已对超大厂首批 800G 量产出货，Q2 起放量、Q3 显著增长；月产能近 10 万只 800G；但 **TTM 仍净亏（-3820 万、EPS -0.64）**，P/S>25——典型高弹性、未盈利叙事股。
- COHR/LITE：CPO（6.4T 硅光）、1.6T 可插拔原型，环节整体受 800G/1.6T 需求拉动。

## 估值风险地图

| 信号 | 现状 | 含义 |
|---|---|---|
| 指数集中度 | 前五占 30% | 系统性回撤放大器 |
| 循环融资 | NVDA-OpenAI-Oracle-CoreWeave | 收入互相做高，脆弱 |
| Capex 修正 | 2026 由 4650→5270 亿，NVDA 谈到 4 万亿/年 | 预期过度乐观风险 |
| OpenAI 估值 | 2023 约 800 亿→2026 初约 7300 亿，9x；累计经营亏损 1400 亿（至 2029） | 终端需求兑现存疑 |

## 可证伪假设 / 跟踪指标

- **景气见顶信号**：① 任一超大厂下调 capex 指引；② MU/HBM 出现现货价松动或合约违约；③ 光模块库存周转恶化、毛利率环比下行；④ NVDA 数据中心环比增速明显放缓。出现 ≥2 个即应主动降弹性仓。
- **健康信号**：超大厂 capex 维持上修 + 龙头 backlog 继续扩张 + 毛利率稳定。

## 风险

- 估值对利率与情绪敏感；2026 信用收紧 + 估值高位可能触发急跌。
- 亏损叙事股（AAOI 类）在情绪退潮时回撤幅度远大于龙头。
- "循环交易"若被监管或会计质疑，板块估值体系受冲击。

## 下一步（可回测）

- 用现有数据（NVDA/SPY 已在库）回测"动量 + 回撤保护"在 AI 龙头上的表现；扩充 AVGO/MU/TSM/MRVL 后做相关性矩阵，量化板块集中度（与课题4联动）。

## 来源

- [NVIDIA Q1 FY27 8-K (SEC)](https://www.sec.gov/Archives/edgar/data/0001045810/000104581026000051/q1fy27pr.htm)
- [Marvell Q1 FY27 8-K (SEC)](https://www.sec.gov/Archives/edgar/data/0001835632/000183563226000014/q127_8kx522026ex-991.htm)
- [US News: 5 best AI memory stocks 2026](https://money.usnews.com/investing/articles/5-best-ai-memory-stocks-to-buy-for-2026)
- [TechTimes: Micron HBM sold out, June 24 earnings](https://www.techtimes.com/articles/318017/20260608/micron-stock-climbs-hbm-sells-out-june-24-earnings-decides-ai-memory-trade.htm)
- [24/7 Wall St: AAOI +439%](https://247wallst.com/investing/2026/06/01/applied-optoelectronics-is-up-439-in-2026-is-it-outperforming-other-optics-stocks-like-lumentum-and-coherent/)
- [Bloomberg: AI circular deals](https://www.bloomberg.com/graphics/2026-ai-circular-deals/)
- [FXEmpire: AI bubble 2026 credit stress](https://www.fxempire.com/forecasts/article/ai-market-faces-2026-test-as-credit-stress-and-valuations-peak-1569164)
- [Investing.com: 2026 another year AI bubble not bursting](https://www.investing.com/analysis/2026-another-year-of-ai-bubble-not-bursting-200672634)
- [Investing.com: beyond Nvidia 5 semis 2026](https://www.investing.com/analysis/beyond-nvidia-5-semiconductor-stocks-set-to-dominate-2026-200671270)
