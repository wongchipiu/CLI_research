# Quant Research Console

`CLI_research` 与相邻 `gpt_quant` 的本地可视化操作台原型。本目录作为
`CLI_research` 的独立前端子包维护：它有自己的 Node 依赖、构建流程和本地部署配置，
但不复制 Python 研究、回测或验证逻辑。

它面向两类用户：

- 普通使用者通过向导、表单、状态卡和结果表完成研究，不需要手写命令。
- 有技术基础的使用者打开“专家模式”，可以看到每个页面动作对应的 CLI 命令，并在“操作手册”中搜索和复制。

## 当前版本

当前版本完成了完整的信息架构和交互原型：

- 工作台
- 目标研究案例（含“每月收益 10%”可检验流程）
- 公开申报研究实验室（13F / Congress PTR 命题、覆盖与当前结论）
- 数据中心
- 策略研究
- 每日美股雷达
- 结果中心
- 模拟账户
- 风险控制
- 专项分析
- 命令操作手册

页面目前不会直接执行本机 CLI。运行按钮保持锁定，直到后续加入经过允许列表和参数验证的本地桥接服务。这样可以先确认页面流程和安全边界，再开放写入研究结果、消耗最终测试或修改模拟账本的动作。

## 本地运行

```bash
cd /Users/brucehuang/Documents/CLI_research/apps/quant-research-console
npm install
npm run dev
```

浏览器打开 `http://localhost:3000`。

## 构建

```bash
npm run build
```

详细设计见 [系统设计](docs/SYSTEM_DESIGN.md)，CLI 使用说明见 [命令手册](docs/COMMAND_MANUAL.md)。
