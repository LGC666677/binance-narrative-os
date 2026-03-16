# 币安叙事中枢

`币安叙事中枢` 是一套面向币安生态的可复用 OpenClaw skill，用来把分散的公开信号整理成一份可消费、可展示、可二次复用的叙事情报报告。

它不直接回答“该买哪一个币”，而是重点解决下面几类问题：

- 市场现在真正成形的主线是什么
- 热度有没有被资金确认
- 哪些叙事是在强化、延续或转弱
- 哪条链正在承接新一轮主题轮动
- 哪些主题更像伪叙事，应该降权观察
- 如何把这些结果直接转成日报、Square 内容和 demo 展示

## 2.0 新增能力

相较于早期单次报告版本，2.0 主要补齐了“连续观察”和“可复用输出”：

- `narrative_memory`：把当前结果与历史快照对比，识别新出现、强化、转弱、回归
- `narrative_rotation_map`：识别链间轮动热度、上升主题和衰退主题
- `narrative_quality_board`：平衡广度、可交易性、确认度和风险
- `risk_of_false_narratives`：识别“热度跑在资金前面”的伪叙事
- `narrative_playbooks`：给研究、内容、风控等角色输出动作建议
- `editorial_calendar`：把实时叙事和官方催化转成内容日历
- `history` 快照：让系统具备时间维度，而不是只看一次截面

## 项目结构

- `SKILL.md`：给 OpenClaw 的 skill 说明
- `agents/openai.yaml`：skill 在界面中的展示元数据
- `scripts/binance_narrative_os.py`：主生成脚本
- `assets/report_template.html`：编辑部风格 demo 模板
- `references/data-sources.md`：数据源与输出模块说明
- `references/product-logic.md`：评分逻辑与产品结构说明
- `config.example.json`：默认配置
- `demo/`：提交演示与 GitHub Pages 使用的示例输出
- `output/`：本地生成输出目录

## 安装依赖

```powershell
py -3 -m pip install -r requirements.txt
```

## 生成实时报告

```powershell
py -3 scripts/binance_narrative_os.py `
  --config config.example.json `
  --json-output output/latest_report.json `
  --markdown-output output/latest_report.md `
  --html-output output/latest_report.html
```

## 生成 demo 演示文件

```powershell
py -3 scripts/binance_narrative_os.py `
  --config config.example.json `
  --json-output demo/sample_report.json `
  --markdown-output demo/sample_report.md `
  --html-output demo/index.html
```

## GitHub demo 自动刷新

仓库内置 `.github/workflows/refresh-demo.yml`，默认能力包括：

- 定时重新生成 `demo/latest_report.json`
- 同步刷新 `demo/latest_report.md`
- 让 `demo/sample_report.*` 跟最新快照保持一致
- 自动提交更新后的 demo 文件

当前默认定时频率是每 15 分钟一次。如需调整，直接修改 `.github/workflows/refresh-demo.yml` 里的 cron 表达式即可。

## 输出模块

脚本最终会产出一份结构化 JSON，核心模块包括：

- `overview`
- `market_pulse`
- `narrative_radar`
- `narrative_memory`
- `narrative_rotation_map`
- `narrative_quality_board`
- `risk_of_false_narratives`
- `attention_capital_crossovers`
- `signal_watch`
- `official_catalysts`
- `narrative_playbooks`
- `editorial_calendar`
- `daily_brief`
- `square_draft`

## OpenClaw 复用方式

推荐复用路径很直接：

1. 运行脚本生成最新 JSON
2. 让下游 OpenClaw / Bot 直接读取 JSON
3. HTML 只负责展示，不承担二次推理

示例：

```powershell
py -3 scripts/binance_narrative_os.py --json-output output/latest_report.json
```

下游 Agent 或机器人可以直接读取：

- `output/latest_report.json`

并重点复用：

- `narrative_radar`：做主题排序和主线判断
- `narrative_memory`：做变化检测
- `risk_of_false_narratives`：做降权或风险提醒
- `editorial_calendar`：做内容节奏安排
- `square_draft`：做发布前文案初稿

## Demo 设计方向

这套 demo 刻意不做成交易终端，而是做成“编辑部 / 叙事指挥台”：

- 纸感排版，而不是量化交易面板
- 用故事卡片展示主线，而不是单纯 KPI 表
- 用轮动地图和编辑日历，替代密集图表堆叠
- 把质量榜、伪叙事风险、信号台组织成内容工作流

这样它可以与另外两套项目保持明显区隔：

- `Alpha`：偏量化数据看板
- `Trade Preflight`：偏交易前安全与风险控制
