# IBKR 账户级日损熔断器

该服务是一个不依赖 LLM 的确定性守护程序。默认配置只读、只允许 Paper 环境；它不会通过 ChatGPT 插件下单。M6-S2 的夜间部署与接口验收见 [M6-S2 验收记录](milestones/m6-s2-ibkr-paper-risk-guard.md)。

## 已实现规则

以 IBKR 账户 `DailyPnL / 当日起始净值` 为判断口径，纽约交易日内状态只能升级：

| 日损失 | 动作 |
|---|---|
| 3% | 进入 `FREEZE`，周期性取消全部活动委托 |
| 4% | 进入 `REDUCE`，取消活动委托并将每个股票多头/空头降至触发前的 50% |
| 5% | 进入 `LIQUIDATE`，取消活动委托并把全部股票多头/空头降至零 |

每个阈值必须由两个连续 P&L 更新确认。状态和目标仓位写入 `var/live_risk/state.json`；进程重启后继续执行原目标，不会在同一交易日自动解锁。P&L 超过10秒未更新时，不根据旧数据猜测清仓，但会进入不健康状态、告警并取消活动委托。

第一阶段只管理 `STK`。期权、期货、外汇和债券不会被自动处理。

## 1. 先运行离线仿真

```powershell
uv run pytest -q tests/test_live_risk.py
uv run python scripts/simulate_live_risk.py
```

仿真不连接IBKR，应依次显示 `NORMAL → FREEZE → REDUCE → LIQUIDATE`，最终股票仓位为零。

## 2. 安装官方 TWS API Python Client

只使用 [IBKR官方TWS API下载](https://interactivebrokers.github.io/) 中的 Python Client，不从 PyPI 安装同名第三方包。接受IBKR许可并解压后，将 `source/pythonclient` 安装到本项目虚拟环境。

Windows示例：

```powershell
uv sync --dev
uv pip install --python .venv\Scripts\python.exe "C:\TWS API\source\pythonclient"
uv run python -c "import ibapi; print('ibapi ok')"
```

macOS/Linux示例：

```bash
uv sync --dev
uv pip install --python .venv/bin/python "/path/to/TWS API/source/pythonclient"
uv run python -c "import ibapi; print('ibapi ok')"
```

## 3. 配置 TWS 或 IB Gateway 的 Paper 会话

先登录模拟账户，再打开 API 设置：

1. 启用 `ActiveX and Socket Clients`。
2. Dry-run阶段可保持 `Read-Only API`；准备测试模拟下单时再关闭只读。
3. TWS Paper默认端口通常是 `7497`；IB Gateway Paper通常是 `4002`，以界面实际设置为准。
4. 只允许本机 `127.0.0.1` 连接。
5. 启用 `Prepare portfolio PnL data when downloading positions`。
6. 启用自动重启，并确认每周重新认证安排。

IBKR会发生日常维护断线。代码对1100/1101/1300连接事件采用断开、重连并重建全部订阅的方式处理。

## 4. 创建本地配置

不要直接修改示例文件：

```powershell
Copy-Item config/live_risk.paper.example.yaml config/live_risk.paper.yaml
```

至少修改：

```yaml
broker:
  expected_account: "DU你的完整模拟账户号"
  port: 7497
  dry_run: true
```

`config/live_risk.paper.yaml`、运行状态和日志均已加入 `.gitignore`。

## 5. 只读连通性测试

先做不连接 TWS 的本地预检：

```bash
.venv/bin/python scripts/run_live_risk.py --config config/live_risk.paper.yaml --preflight
```

必须看到 `ready: true`。它检查 Paper 环境、精确 `DU` 账户、本机地址、绝对运行路径及官方 `ibapi`，但不会连接账户或发单。

```powershell
uv run python scripts/run_live_risk.py --config config/live_risk.paper.yaml --once
```

确认：

- 连接的是精确的 `DU` 账户；
- `var/live_risk/status.json` 中 `healthy` 为 `true`；
- `daily_pnl`、`net_liquidation` 和持仓数量正确；
- TWS没有收到撤单或交易请求。

连续只读运行：

```powershell
uv run python scripts/run_live_risk.py --config config/live_risk.paper.yaml
```

连接或循环异常时，即使拿不到新账户快照，服务也会把 `live_risk_status` v1 写成 `healthy=false`。仅看到进程存在不等于仍受保护，应同时监控 `status.json.updated_at` 和 `healthy`。

## 6. Paper下单验收

只在模拟账户完成以下操作：

1. 建立少量、可承受的测试股票仓位。
2. 在配置中将 `dry_run` 改成 `false`。
3. 确认账户号以 `DU` 开头且完全匹配。
4. 先用调整后的临时阈值进行受控测试，观察撤单、50%减仓、最终清仓和部分成交复核。
5. 恢复3%/4%/5%阈值，至少连续运行五个交易日。

运行文件：

- `var/live_risk/status.json`：当前健康与风控状态；
- `var/live_risk/state.json`：不可随意删除的当日熔断锁；
- `var/live_risk/audit.jsonl`：每次阈值、撤单和下单的不可覆盖审计记录；
- `var/live_risk/service.log`：连接与异常日志。

如设置 `LIVE_RISK_WEBHOOK_URL`，重大风险事件会额外发送JSON POST通知。Webhook失败不会阻止本地风险动作。

## 7. macOS 夜间守护

先在前台完成只读和 Paper 小仓位验收，再生成 launchd 配置；生成器只写 plist，不会自动安装或启动服务：

```bash
cd /Users/brucehuang/Documents/CLI_research
.venv/bin/python scripts/render_live_risk_launchd.py \
  --config config/live_risk.paper.yaml \
  --output var/live_risk/com.quant.live-risk-paper.plist
plutil -lint var/live_risk/com.quant.live-risk-paper.plist
```

plist 使用绝对路径、`KeepAlive` 和 `/usr/bin/caffeinate -im`。确认内容后，再由你手工复制到 `~/Library/LaunchAgents/` 并用 launchd 加载；本项目不会替你修改系统服务。

重要限制：`caffeinate` 能阻止普通空闲睡眠，但**不能保证合盖后的 Mac 继续运行**。夜间保护要求 Mac 接电、保持开盖且 TWS/IB Gateway 已登录并配置自动重启；更稳妥的长期形态是经 Paper 验收后部署到始终在线的受控主机。TWS/IB Gateway 的每周重新认证仍需人工安排。

## 实盘保护

实盘下单默认被锁死。即使未来修改为 `environment: live`，也必须同时满足：

1. `dry_run: false`；
2. `allow_live_trading: true`；
3. `expected_account`精确匹配；
4. 环境变量 `IBKR_LIVE_TRADING_ACK=ALLOW:<精确账户号>`。

当前交付只验收Paper，不应开启上述实盘条件。自动API交易可能还涉及IBKR地区实体、账户权限或算法登记要求，实盘前需向IBKR确认。

## 已知边界

- `MKT DAY`股票单在停牌、闭市或无流动性时无法保证成交。
- 账户损失阈值是触发器，不是成交价格保证；跳空可能让实际损失显著超过阈值。
- 默认 `outside_rth: false`；盘前盘后触发会保持锁定并等待可执行时段，不能保证以5%损失成交。
- `reqGlobalCancel`会撤销人工和其他API客户端的所有活动订单，这是有意的强制风险行为。
- 本程序能阻止自己的策略继续开仓，并周期性撤单，但不能禁止人在TWS里重新手工下单；清仓锁定后出现的新股票仓位会再次被关闭。
- 当日起始净值由首次有效快照的 `NetLiquidation - DailyPnL` 推导。入出金、跨市场P&L重置和虚拟外汇显示设置必须在Paper验收时核对。
