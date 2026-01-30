我下一步是要做agent技术实现



对，你这份 PDF 的实现思路**必须先做“买家类型分流”**，再跑各自的核验流水线——这在文档里是明确拆成 **「公司买家类型 360洞察流程图」**和**「个人买家类型 360洞察流程图」**两套的。 

下面我按“Agent 技术实现”给你一套**可直接开工的架构**：Router + Skills + 工具接口（MCP/Tools）+ 产出 Schema + 评分规则 + 编排伪代码。

---

## 1) 总体架构：Router → 两条 Pipeline

### 1.1 Buyer Type Router（必须第一步）

**判断输入属于：Company Buyer / Individual Buyer / Mixed（公司+联系人）**

**依据（来自文档的信息形态）**

* 公司买家典型输入：公司名称 / 官网 / 公司电话 / 公司社媒公司页（LinkedIn company / FB page）等。
* 个人买家典型输入：姓名、职位、所在地、LinkedIn 个人主页、个人 FB、个人简介等。 

**Router 输出**

```json
{
  "buyer_type": "company|individual|mixed",
  "normalized_inputs": {
    "company": {...},
    "person": {...}
  },
  "missing_fields": ["..."]
}
```

---

## 2) 两条 Pipeline 的 Skill 切分（按你 PDF 的核验项 & 维度）

### A) 公司买家核验 Pipeline（Company Buyer Track）

> 目标：验证企业真实性 + 业务匹配 + 采购能力/机会 + 增长信号
> 文档给的核心数据来源：官网/Google/GPT、LinkedIn 公司页、FB 企业页、海关交易数据等。

#### Skill A1：企业实体与可信度（Company Entity Credibility）

来自文档“维度1：客户真实性与基本面评估”里的 1.1。

* 输入：company_name, country(optional)
* 工具：web_search/serp、company_site_fetch、linkedin_company_fetch
* 核验点：公司类型/所在地/成立时间/官网信息一致性（公司实体判断：制造/贸易/皮包）。
* 输出：credibility_score, red_flags

#### Skill A2：业务匹配度（Business Fit）

来自文档 1.2。

* 输入：company主营业务、产品/服务清单、我方产品线
* 输出：fit_score、推荐切入点

#### Skill A3：合作路径推断（Cooperation Mode Inference）

来自文档“维度2：潜在合作路径分析”2.1。

* 输入：业务范围、合作客户清单
* 输出：更像 OEM/ODM 还是渠道合作 + 对应销售策略

#### Skill A4：需求挖掘切入点（Need Mining）

来自文档 2.2。

* 输入：现有产品/服务清单
* 输出：产品线空白/替换升级机会

#### Skill A5：贸易/海关能力核验（Trade & Customs Verification）

文档明确写了：看交易笔数判断进口经验，用海关编码看行业经验。

* 输入：company_name, target_industry_hscode(optional)
* 工具：customs_trade_fetch
* 输出：trade_experience(true/false)、volume_level、hscode_match、insights

#### Skill A6：官网域名核验（Website Domain Verification）

文档多处强调“用官网域名地址核验即可”。

* 输入：website_url, email(optional)
* 工具：whois/domain_intel、site_fetch
* 输出：domain_trust_score、official_status、email_domain_match

#### Skill A7：企业活跃度与增长信号（Activity & Growth Signals）

来自“企业活力与成长性判断”（内容在文档后续维度段落）。

* 输入：公司动态（LinkedIn posts / FB posts）、员工规模变化（若可抓）
* 输出：growth_stage（expanding/stable/declining）、priority_level

---

### B) 个人买家核验 Pipeline（Individual Buyer Track）

> 目标：确认“是不是这个人” + “是不是这个岗位” + “是否同名误伤” + “沟通策略”
> 文档给了典型个人字段：姓名/职位/所在地/LinkedIn、FB、个人简介、技能、推荐信、语言等。 

#### Skill B1：身份匹配与同名消歧（Identity Match & Disambiguation）

文档专门用“另一个同名 Ayaz Arshad 的 FB 页面”做示例，强调同名问题。 

* 输入：name, location(optional), social_urls
* 工具：linkedin_profile_fetch、facebook_profile_fetch、twitter_profile_fetch
* 输出：identity_confidence、same_name_candidates、disambiguation_notes

#### Skill B2：职位核验（Role Verification）

文档里个人核验项多次写“用具体职位核验即可”。

* 输入：claimed_position, company_name, linkedin_profile
* 输出：role_confidence、seniority_level、decision_power_guess

#### Skill B3：职业路径与专业实力（Career Credibility）

文档列出工作经历/教育/认证/技能/推荐信等。

* 输出：professional_score、stability_flags

#### Skill B4：沟通偏好与破冰线索（Comms Preference）

文档强调语言能力、个人兴趣、动态评论等可以用于沟通切入。 

* 输出：preferred_language、icebreakers、tone_suggestion

#### Skill B5：风险信号检测（Fraud / Low-Value Signals）

文档给了“gmail vs 公司邮箱”对照（[ayaz.arshad@gmail.com](mailto:ayaz.arshad@gmail.com) 与公司域邮箱）。

* 输出：risk_flags（free_email, domain_mismatch, inconsistent_employment…）

---

## 3) 你落地时的 Tool（MCP）设计：最低可用 6 个工具

你做 agent 实现时，不需要一口气做全网采集，先用 **6 个 MCP tools** 就能跑通两条 Pipeline：

1. `serp_search(query, locale)`：Google/Bing 搜索摘要（公司/人）
2. `fetch_url(url)`：抓官网/博客/联系页内容
3. `linkedin_company_fetch(url|name)`：公司页结构化信息（行业、规模、成立等）
4. `linkedin_profile_fetch(url|name)`：个人页结构化信息（职位、经历、教育等）
5. `social_profile_fetch(platform, url)`：FB/Twitter 等（基础字段+活跃度）
6. `customs_trade_fetch(company_name, years=3)`：海关交易摘要（笔数、HS code、金额区间）

> 文档里“公司官网/Google&GPT/LinkedIn/FB/TW/海关”就是这套工具要覆盖的来源集合。 

---

## 4) 统一输出：一个“核验报告 Schema”，两条链路都能写进去

```json
{
  "buyer_type": "company|individual|mixed",
  "overall": {
    "score": 0-100,
    "risk_level": "low|medium|high",
    "confidence": "high|medium|low"
  },
  "company": {
    "identity": {...},
    "website_domain": {...},
    "social_consistency": {...},
    "trade_customs": {...},
    "business_fit": {...},
    "growth_signals": {...}
  },
  "individual": {
    "identity_match": {...},
    "role_verification": {...},
    "professional_credibility": {...},
    "comms_preference": {...},
    "risk_signals": {...}
  },
  "recommended_next_actions": [
    "下一步要问客户的3个问题",
    "建议联系的岗位/部门",
    "建议推进路径（OEM/现货/渠道…）"
  ],
  "evidence": [
    {"source":"linkedin", "url":"...", "field":"employee_size", "value":"11-50"},
    {"source":"customs", "field":"transactions_3y", "value":316}
  ]
}
```

---

## 5) 编排（Orchestration）伪代码：Router + 并行 Skills + 汇总打分

```python
def run_due_diligence_agent(raw_input):
    route = buyer_type_router(raw_input)

    results = {"buyer_type": route.buyer_type}

    if route.buyer_type in ["company", "mixed"]:
        company = route.normalized_inputs["company"]
        results["company"] = parallel(
            entity_credibility(company),
            website_domain_verify(company),
            social_consistency_company(company),
            trade_customs_verify(company),
            business_fit(company),
            growth_signals(company),
        )

    if route.buyer_type in ["individual", "mixed"]:
        person = route.normalized_inputs["person"]
        results["individual"] = parallel(
            identity_disambiguation(person),
            role_verification(person),
            professional_credibility(person),
            comms_preference(person),
            risk_signals_person(person),
        )

    results["overall"] = score_and_rank(results)
    results["recommended_next_actions"] = action_recommender(results)
    return results
```

---

## 6) 评分建议：让“核验项”真正可用

你文档里“核验项”的风格更像 checklist（例如：域名核验、按国家/地区匹配、职位核验、交易笔数/海关编码核验）。 
落地时建议改成**可解释的评分**：

### 公司（示例权重）

* 企业实体可信度 30%
* 贸易/海关能力 25%
* 官网域名可信度 15%
* 业务匹配&合作路径 20%
* 活跃度&增长 10%

### 个人（示例权重）

* 身份匹配/同名消歧 30%
* 职位核验&决策权 35%
* 职业可信度 15%
* 风险信号 20%

---

## 7) 你现在最该先做的 2 个 MVP

为了最快跑通“端到端”：

1. **MVP-1：Router + 基础核验报告**

* Router（company/individual/mixed）
* Company：官网域名核验 + LinkedIn 公司页抓取 + 贸易能力（先用 stub 数据也行）
* Individual：LinkedIn 职位核验 + gmail/公司域邮箱风险提示

2. **MVP-2：把“核验项”变成“可解释评分”**

* 输出 score + reason + evidence（证据 URL/字段）

---

如果你愿意我可以下一条直接给你：

* **Buyer Type Router 的规则/提示词模板**（能稳定分流）
* 每个 Skill 的 **tool-call contract（JSON schema）**
* 以及一个最小可运行的 **Node/Python agent skeleton**（带并行、重试、证据缓存、评分器）

你实现栈打算用什么？（LangGraph / AutoGen / 自研 Orchestrator / Dify / 其他）我可以按你的栈把上面这套“写成能跑的工程结构”。
