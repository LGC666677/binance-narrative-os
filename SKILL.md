---
name: binance-narrative-os
description: 聚合 Topic Rush、社媒热度、聪明钱流入、聪明钱信号、代币审计与币安官方公告，生成可复用的币安叙事情报报告。适用于热题材追踪、链间轮动、催化映射、伪叙事识别与内容策划。
---

# 币安叙事中枢

## 概述

这套 skill 面向“叙事情报”，不是直接下单执行。

它会运行本地生成器，把公开的币安生态信号整理成一份可复用报告，核心内容包括：

- 当前最强主线
- 资金确认情况
- 与历史快照相比的变化
- 链间轮动
- 伪叙事风险
- 可直接发布或展示的编辑输出

## 适用场景

当用户有下面这些需求时，应该使用这套 skill：

- 解释币安生态当前最强的叙事主线
- 对比热度与资金确认是否一致
- 判断不同链之间的叙事轮动
- 识别脆弱主题或疑似伪叙事
- 生成可发 Square 的叙事摘要
- 制作适合演示或参赛提交的叙事看板与报告

## 核心流程

1. 运行 `scripts/binance_narrative_os.py`
2. 优先把生成的 `JSON` 当作唯一事实源
3. `Markdown` 和 `HTML` 只负责展示
4. 如果部分接口失败，保留报告主体，并在 `warnings` 中显式暴露问题

## 运行手册

### 生成最新报告

```powershell
py -3 scripts/binance_narrative_os.py `
  --config config.example.json `
  --json-output output/latest_report.json `
  --markdown-output output/latest_report.md `
  --html-output output/latest_report.html
```

### 生成 demo 演示文件

```powershell
py -3 scripts/binance_narrative_os.py `
  --config config.example.json `
  --json-output demo/sample_report.json `
  --markdown-output demo/sample_report.md `
  --html-output demo/index.html
```

## 复用规则

- 下游 Agent 优先读取 `JSON`
- 如果报告已经生成，不要重复从原始接口重建同一套推理
- 用 `narrative_radar` 做主题排序与主线判断
- 用 `narrative_memory` 做跨时间变化识别
- 用 `risk_of_false_narratives` 做降权和风险提醒
- 用 `narrative_playbooks`、`editorial_calendar` 和 `square_draft` 支撑内容生产

## 附带资源

### `scripts/`

- `binance_narrative_os.py`：主生成脚本

### `references/`

- `data-sources.md`：数据源、接口来源与输出模块
- `product-logic.md`：评分模型与产品结构说明

### `assets/`

- `report_template.html`：编辑部风格 demo 界面
