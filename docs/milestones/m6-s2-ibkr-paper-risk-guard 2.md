# M6-S2：IBKR Paper 夜间自动止损接口与守护

状态：**代码完成；等待用户本机 Paper 配置与连通验收（2026-08-29）。**

## 用户目标

用户位于中国时区，午夜后无法持续观察美股账户。本条目交付一个无需 LLM 在线、可在用户睡眠时连续运行的确定性账户级止损服务：读取 IBKR Daily P&L、净值和持仓，达到阈值后撤单、减仓或清仓，并留下可审计状态。

## 本条目边界

- 复用现有 3% `FREEZE`、4% `REDUCE`、5% `LIQUIDATE` 单向升级规则；默认连续两次新鲜 P&L 才触发。
- 只管理股票 `STK`，通过官方 TWS API 提交 close-only `MKT DAY` 订单。
- 首次交付只允许 `DU` Paper 账户执行；实盘三重保护保持锁定，本轮不替用户开启。
- 新增 macOS launchd 配置生成器，以 `caffeinate` 包裹服务，避免普通空闲睡眠暂停进程；不自动安装或加载系统服务。
- 连接失败、P&L 陈旧和循环异常必须把健康状态原子写入 `status.json`，使“守护进程还在但已经失去保护”可被发现。
- 为 TWS 订单 ID、close-only 方向、订单字段、账户匹配和连接状态回调补隔离测试，不需要真实账户。

## 不在本条目

- 不自动登录 TWS/IB Gateway，不保存密码、验证码或账户密钥。
- 不部署到 VPS，不修改 macOS 电源设置，不替用户执行 `launchctl`。
- 不实现个股固定/追踪止损单。它属于另一套风险语义，且会与账户熔断时的全局撤单发生冲突，应在本条目 Paper 连续验收后单独设计。
- 不保证止损成交价格。停牌、跳空、闭市、无流动性、TWS/网络断线或 IBKR 维护均可能延迟或劣化成交。

## 验收条件

1. 离线仿真仍覆盖冻结、减半、清仓、部分成交、重启和陈旧数据。
2. 假 TWS API 验证 exact-account、订单 ID 单调、平多卖出/平空买入、`MKT DAY`、`transmit=true` 和断线回调。
3. 运行循环异常后健康文件明确为 `healthy=false`，重连后恢复。
4. launchd plist 只引用绝对项目/配置路径，包含自动重启、日志和 `caffeinate`；生成操作不加载服务。
5. 两仓全量测试通过；不连接真实 TWS、不提交任何真实或 Paper 订单。

## 实现与本机验收

- `TwsBroker` 只允许 `risk-` 引用的股票平仓，拒绝超出当前持仓的数量；平多为 `SELL`、平空为 `BUY`。
- `nextValidId`、`openOrder`、`orderStatus` 共同推进单调订单 ID；1101/1102 和 `connectionClosed` 更新连接健康。
- 无账户快照的连接/循环失败也写出 `live_risk_status` v1；恢复后重新写健康快照并发恢复事件。
- 新增只读 `--preflight` 和不自动安装的 launchd plist 生成器。
- 离线仿真最终进入 `LIQUIDATE`；`CLI_research` 100 项 pytest、`gpt_quant` 31 项 unittest 通过，编译和差异检查通过。
- 本机当前没有 `config/live_risk.paper.yaml`，也未安装官方 `ibapi`；因此没有连接 TWS、没有提交 Paper/实盘订单。

## 官方接口依据

- [订单提交与订单 ID](https://interactivebrokers.github.io/tws-api/order_submission.html)：新订单 ID 必须高于已看到的订单回调 ID，订单状态由 `openOrder`/`orderStatus` 返回。
- [账户 P&L 订阅](https://interactivebrokers.github.io/tws-api/pnl.html)：账户级 Daily P&L 通过 `reqPnL`/`pnl` 更新，其重置口径受 TWS 配置影响。
- [连接消息码](https://interactivebrokers.github.io/tws-api/message_codes.html)：1100 表示连接丢失，1101 恢复但订阅数据丢失，1102 恢复且数据保持，1300 表示 socket 端口变化并断开。
