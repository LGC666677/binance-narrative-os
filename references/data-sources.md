# 数据来源

## 币安 Web3 公开接口

- `Topic Rush`
  - `GET /bapi/defi/v1/public/wallet-direct/buw/wallet/market/token/social-rush/rank/list`
  - 用于主题发现、进度判断、净流入、主题深度以及关联代币提取

- `Social Hype Leaderboard`
  - `GET /bapi/defi/v1/public/wallet-direct/buw/wallet/market/token/pulse/social/hype/rank/leaderboard`
  - 用于社媒注意力、情绪、热度变化速度等指标

- `Unified Rank`
  - `POST /bapi/defi/v1/public/wallet-direct/buw/wallet/market/token/pulse/unified/rank/list`
  - 用于获取 `trending`、`top_search` 等综合榜单

- `Smart Money Inflow Rank`
  - `POST /bapi/defi/v1/public/wallet-direct/tracker/wallet/token/inflow/rank/query`
  - 用于资金确认与聪明钱流入排序

- `Smart Money Signals`
  - `POST /bapi/defi/v1/public/wallet-direct/buw/wallet/web/signal/smart-money`
  - 用于构建可映射回叙事主题的信号台

- `Token Audit`
  - `POST /bapi/defi/v1/public/wallet-direct/security/token/audit`
  - 用于合约验证、税率风险、潜在风险标签补充

## 币安官方内容层

- `CMS article list`
  - `GET /bapi/composite/v1/public/cms/article/list/query`

- `CMS article detail`
  - `GET /bapi/composite/v1/public/cms/article/detail/query`

这部分数据作为“官方催化层”，避免整套叙事分析只依赖社媒热度或链上资金。

## 输出模块

脚本会产出下列核心模块：

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
