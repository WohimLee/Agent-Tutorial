太好了，这个 PDF 本身就是一个**非常完整的 B2B 背调方法论蓝图**。我不是泛泛地“写几个技能名”，而是**严格按你这套 360 洞察流程图，把它拆成一组可直接给 Agent 用的「B2B 背调核验 Skills」**，每个 Skill 都是**可落地、可组合、可评分**的。

下面是**Skill 设计稿（偏产品 / Agent 架构视角）**，不是 PPT 文案。

---

# B2B 背调核验 Skills 设计（基于 360 洞察流程）

> 目标：
> **判断一个 B2B 客户「是不是人」「靠不靠谱」「值不值得跟」「怎么跟」**

---

## Skill 总览（推荐拆成 8 个核心 Skills）

```
Company Identity Verification
├─ Company Basic Authenticity Skill
├─ Website & Domain Verification Skill
├─ Social Presence Consistency Skill
├─ Trade & Customs Capability Skill
├─ Business Match & Opportunity Skill
├─ Supply Chain & Competition Skill
├─ Growth & Activity Signal Skill
└─ Decision Maker Verification Skill
```

---

## Skill 1：企业基础真实性核验

### `Company_Basic_Authenticity_Skill`

### 🎯 核验目标

> 这家公司是不是**真实存在的企业实体**，而不是皮包/空壳/伪造信息。

### 输入

```json
{
  "company_name": "",
  "country": ""
}
```

### 核验维度（来自 PDF）

* 公司名称（多来源一致性）
* 公司类型（制造商 / 贸易商 / 服务商）
* 成立时间
* 所在国家 / 地区
* 行业归属
* 员工规模（LinkedIn）

### 核验逻辑

* 官网 + Google + GPT 多源交叉
* LinkedIn 公司页信息匹配
* 成立时间与业务规模是否逻辑自洽

### 输出

```json
{
  "authenticity_score": 0-100,
  "risk_flags": [],
  "confidence_level": "high | medium | low",
  "summary": "企业实体真实性判断结论"
}
```

📌 对应 PDF「维度1：客户真实性与基本面评估」

---

## Skill 2：官网与域名核验

### `Website_Domain_Verification_Skill`

### 🎯 核验目标

> 官网上的信息是不是**官方、长期、可信**。

### 输入

```json
{
  "website_url": ""
}
```

### 核验点

* 域名与公司名是否强相关
* 是否为企业官网（非博客 / 落地页）
* 联系方式完整性（电话 / 地址 / 邮箱）
* 官网信息与 LinkedIn / FB 是否一致

### 输出

```json
{
  "domain_trust_score": 0-100,
  "official_status": true/false,
  "anomalies": []
}
```

📌 对应 PDF「用官网域名地址核验即可」

---

## Skill 3：社媒一致性核验

### `Social_Presence_Consistency_Skill`

### 🎯 核验目标

> 同一个公司，在不同平台是不是**同一个“人设”**。

### 输入

```json
{
  "linkedin_url": "",
  "facebook_url": "",
  "twitter_url": ""
}
```

### 核验点

* 公司名 / 行业 / 地址一致性
* 创建时间是否合理
* 粉丝数 vs 员工规模
* 内容是否长期更新

### 输出

```json
{
  "consistency_score": 0-100,
  "active_channels": [],
  "suspicious_signals": []
}
```

📌 对应 PDF「社媒运营能力与C端影响力评估」

---

## Skill 4：海关与贸易能力核验

### `Trade_Customs_Capability_Skill`

### 🎯 核验目标

> **有没有真实采购 / 进口经验**，是不是“嘴上公司”。

### 输入

```json
{
  "company_name": "",
  "industry": ""
}
```

### 核验点

* 近 3 年交易笔数
* 海关编码是否匹配行业
* 采购国家 / 供应商分布
* 订单金额与数量结构

### 输出

```json
{
  "trade_experience": true/false,
  "trade_volume_level": "low | medium | high",
  "industry_match": true/false,
  "insights": []
}
```

📌 对应 PDF「通过交易笔数看是否有进口经验」

---

## Skill 5：业务匹配与合作机会判断

### `Business_Match_Opportunity_Skill`

### 🎯 核验目标

> **是不是你的目标客户，值不值得跟进**。

### 输入

```json
{
  "company_business": {},
  "our_product_line": {}
}
```

### 分析点

* 主营业务 vs 我司产品
* 客户产品线空白点
* OEM / ODM / 分销倾向
* 可切入的产品或方案

### 输出

```json
{
  "fit_score": 0-100,
  "recommended_entry_point": "",
  "cooperation_mode": "OEM | ODM | Distribution"
}
```

📌 对应 PDF「业务匹配度 & 潜在合作路径分析」

---

## Skill 6：供应链与竞争替代分析

### `Supply_Chain_Competition_Skill`

### 🎯 核验目标

> **我们有没有机会替代现有供应商**。

### 输入

```json
{
  "current_suppliers": [],
  "trade_data": {}
}
```

### 分析点

* 供应商集中度
* 单一供应商风险
* 价格 / 质量 / 交期对比空间

### 输出

```json
{
  "replacement_opportunity": "low | medium | high",
  "attack_angle": ["price", "quality", "delivery", "service"]
}
```

📌 对应 PDF「供应链稳定性与可替代性分析」

---

## Skill 7：企业活跃度与成长性判断

### `Growth_Activity_Signal_Skill`

### 🎯 核验目标

> 这是一个**在增长的客户，还是在躺平的客户**。

### 输入

```json
{
  "social_activity": {},
  "company_updates": {}
}
```

### 信号

* 动态发布频率
* 员工增长趋势
* 新产品 / 新市场动作

### 输出

```json
{
  "growth_stage": "expanding | stable | declining",
  "priority_level": "high | medium | low"
}
```

📌 对应 PDF「企业活力与成长性判断」

---

## Skill 8：关键决策人核验（B2B 核心）

### `Decision_Maker_Verification_Skill`

### 🎯 核验目标

> **你聊的人是不是对的人**。

### 输入

```json
{
  "person_name": "",
  "claimed_position": "",
  "company_name": ""
}
```

### 核验点

* 职位真实性（LinkedIn）
* 工作经历连续性
* 地区 / 公司匹配
* 多平台身份一致性

### 输出

```json
{
  "role_confidence": 0-100,
  "decision_power_level": "low | medium | high",
  "contact_strategy": ""
}
```

📌 对应 PDF「关键决策人与组织架构洞察」

---

## 最后一句大实话（站在产品视角）

你这个 PDF **不是“数据展示文档”**，而是：

> 👉 一套**可以直接产品化的 B2B 背调 Agent Skill Map**

如果你愿意，下一步我可以帮你：

* 把这 8 个 Skill **写成 MCP Tool Schema**
* 设计 **Skill 编排策略（先验 → 深挖 → 决策）**
* 做一个 **B2B 客户风险 / 价值评分模型**
* 或直接：**帮你写成对外卖的产品 PRD**

你想往 **Agent 产品** 走，还是 **内部销售赋能系统**？
