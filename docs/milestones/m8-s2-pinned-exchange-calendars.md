# M8-S2 版本冻结交易日历验收记录

日期：2026-09-02

## 交付范围

本条目把本地模拟信号与账本从“仅排除周末”升级为版本冻结的交易所 schedule，不连接模型、券商或实盘执行。

1. 两仓精确锁定 `exchange-calendars==4.13.2`，运行时再次核对安装版本，漂移时直接拒绝。
2. 美股使用 XNYS；中国 A 股使用 XSHG schedule，并以 `XSHG+XSHE` 契约身份明确表示 SSE/SZSE 共同的中国内地休市安排。
3. `paper_target_signal` 升级为 schema v4，`calendar_id` 进入 canonical `signal_id`；模拟账户持久化并复核同一身份。
4. 信号 `available_at` 必须等于日历给出的实际 session close，因而支持 XNYS 提前收市；执行时间按 schedule 检查 A 股午休。
5. 生成信号、模拟估值和模拟成交均拒绝交易所休市日；超出冻结版本覆盖范围不做未来推算。

Provider 选择依据：维护方列出的内置日历包含 XNYS 与 XSHG，但没有独立 XSHE；4.13.1 修复了 2026 XSHG 日历，当前冻结在后续 4.13.2。[exchange_calendars README](https://github.com/gerrymanoim/exchange_calendars/blob/master/README.md)、[4.13.2 PyPI](https://pypi.org/project/exchange_calendars/4.13.2/)、[release notes](https://github.com/gerrymanoim/exchange_calendars/releases)

2026 年 SSE 与 SZSE 公布的春节等休市日期一致；NYSE 官方日历确认 7 月 3 日休市及 11 月 27 日 13:00 提前收市。[SSE 休市安排](https://www.sse.com.cn/disclosure/dealinstruc/closed/)、[SZSE Trading Calendar](https://www.szse.cn/www/English/services/trading/calendar/index.html)、[NYSE Holidays & Trading Hours](https://www.nyse.com/trade/hours-calendars)

## 日历身份

```text
美股：exchange_calendars:4.13.2:XNYS
A股：exchange_calendars:4.13.2:XSHG+XSHE
```

`XSHG+XSHE` 不是声称 provider 内置 XSHE，而是显式记录当前两所共用的内地休市 schedule。若未来公告不一致，必须引入独立 XSHE 实现并升级契约。

## 对抗验收

- XNYS 2026-07-03：休市；2026-07-06：开市。
- XNYS 2026-11-27：13:00 美东收市；13:30 模拟执行被拒绝。
- SSE/SZSE 2026-02-23：春节休市；2026-02-24：恢复。
- A 股 12:00 午休：模拟执行被拒绝。
- provider 版本伪装为 4.13.1：拒绝。
- 中国日历请求 2030 年、超出冻结 coverage：拒绝。
- 旧账户删除 `calendar_id` 后加载：拒绝，不静默升级。
- v4 生成方输出可由 gpt_quant 消费方重新计算并接受。

## 验证结果

- `CLI_research`：`.venv/bin/python -B -m pytest -q -p no:cacheprovider` → **120 passed**。
- `gpt_quant`：`PYTHONPATH=src ../CLI_research/.venv/bin/python -B -m unittest discover -s tests -q` → **40 tests OK**。
- 离线 paper demo：首次成交、持久化、重放拒绝、陈旧价格拒绝均通过。
- 两仓依赖文件、编译和 `git diff --check` 通过。

## 迁移与边界

- M8-S1 的 v3 信号和未保存 `calendar_id` 的旧账户必须从原 `metrics.json` 重新创建；不做会掩盖日历版本的自动迁移。
- 日历 schedule 不等于完整交易规则：个股停牌、临时停市、特殊板块和券商撮合仍由其他证据/服务处理。
- provider 的未来日期有限；到 coverage 边界前必须审核上游 release、更新精确版本、重新跑节假日测试并升级 `calendar_id`。
- 没有连接模型、真实行情更新、券商或实盘账户，也没有产生任何收益结论。
