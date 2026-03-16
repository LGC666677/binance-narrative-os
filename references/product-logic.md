# 产品逻辑

## 产品定位

叙事中枢不是交易终端，而是一套面向币安生态的“叙事操作系统”。

它主要解决六件事：

- 识别市场正在讨论什么
- 区分“热度”与“确认”
- 记录相对上一轮快照发生了什么变化
- 判断主题是否在不同链之间轮动
- 标记脆弱、误导或容易失真的主题
- 把分析结果直接变成可发布内容和可展示 demo

## 叙事雷达模型

`narrative_radar` 会从多个维度评价每个主题：

- `attention_score`：注意力强度
- `money_score`：资金确认强度
- `breadth_score`：覆盖广度
- `tradability_score`：可交易性
- `momentum_score`：动量
- `confirmation_score`：确认度
- `fragility_score`：脆弱性
- `quality_score`：质量得分
- `narrative_strength_score`：综合叙事强度

目标不是制造一个神秘总分，而是让每个得分都可解释、可拆解、可复用。

## 主题状态

- `Igniting`：注意力开始出现，但确认仍然偏薄
- `Accelerating`：热度与资金同时增强
- `Confirmed`：强度、质量、确认度都已经站稳
- `Cooling`：确认不足，或资金/流动性边际转弱

## 记忆层

`narrative_memory` 会把当前报告与以下对象对比：

- 上一次本地报告
- `history` 目录中的历史快照

然后把主题标记为：

- `New`：新出现
- `Continuing`：延续
- `Strengthening`：强化
- `Weakening`：转弱
- `Returning`：回归

## 轮动层

`narrative_rotation_map` 重点回答这些问题：

- 哪条链当前承接了最密集的主题集合
- 哪些主题正在冒头
- 哪些主题开始衰退
- 哪些地方是热度领先资金
- 哪些地方是资金领先热度

## 伪叙事风险层

`risk_of_false_narratives` 故意与主排序分开，避免“高热度但高风险”的主题被主榜误导。

风险通常在下面这些条件下升高：

- 流动性偏薄
- 1 小时净流入转负
- 持仓集中度偏高
- 审计风险抬升
- 社媒热度明显跑赢资金确认

## Demo 设计原则

这套项目需要与另外两套投稿在视觉上彻底区分：

- `Alpha`：量化型数据看板
- `Trade Preflight`：交易前安全控制台
- `Narrative OS`：编辑部 / 叙事指挥台

因此 demo 的重心不是大盘图表，而是：

- 故事卡片
- 轮动地图
- 质量榜
- 编辑日历
- Square 草稿
