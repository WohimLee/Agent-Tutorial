## LangSmith 界面


##### 🧭 一句话解释

> **LangSmith 是一个用来观测、调试、评估、回放、管理 LLM 应用的生产级平台
> ——尤其适合多步骤 Agent / Workflow / RAG 系统。**


它的角色大概等价于：

* 🧪 Postman（发请求）
* 🧠 Redux DevTools（看状态流转）
* 🔍 Trace debugger（调试调用栈）
* 📊 APM（运行监控）
* 🕵 Session Replay（回放 + 分析）

全部整合在一起。

---

### 🖥  3 个重要区域

#### 🟣 左侧：Workspace / 功能入口栏

这一列决定你能做哪些事：

##### 常用模块说明

| 模块             | 用来干嘛                        |
| -------------- | --------------------------- |
| 🏠 Home        | 总览                          |
| 📡 Tracing     | 查看历史运行 Trace                |
| 📊 Monitoring  | 监控 LLM 服务性能                 |
| 📁 Datasets    | 构造评测集                       |
| 🧪 Experiments | 做 A/B Test / LLM 评测         |
| 💬 Prompts     | Prompt 管理版本控制               |
| 🤖 Playground  | 单轮 prompt 试验                |
| 🧩 Studio      | 调试 **LangGraph/Agent** (核心) |
| 🚀 Deployments | 部署/环境管理                     |

👉 你现在在 **Studio**

表示正在：

> 交互式调试一个 Agent Workflow

---

#### 🟡 中间：Input + Graph + Memory

这一列是：

> 如何「喂输入」+「看图结构」

##### 你看到的 Input 表单

就是：

> **State schema 自动生成的 UI**

也就是你定义的：

```python
class BGCheckState(TypedDict)
```

被 LangSmith 自动映射成：

* 文本
* JSON
* 列表
* Optional…

你只需要：

✔ 选择要填的字段
✔ 点 Submit

就可以启动一次 workflow

等价于：

```python
graph.invoke(state)
```



##### Graph 视图

展示：

📌 每个节点的执行顺序
📌 输入/输出数据
📌 是否报错
📌 延迟
📌 token 用量（付费调优很关键）


##### Memory 标签

用来：

> 存对话历史 / session 变量

（适合 Agent 聊天模式）



#### 🟢 右侧：Trace / 执行时间线

这里是核心：

> 每一步 LLM / Tool / Node 的运行细节

你可以看到：

✔ init_task
✔ mq_reply
✔ state 变化
✔ 消息流转

比如你截图中的：

```
Turn 2
  __start__
  init_task
       Company Name Raw = 测试公司
       Thread Id = ...
       Report Json = ...
  mq_reply
```

这非常适合：

* Debug 数据传递
* 排查 LLM 错误
* 定位 Token 爆炸来源
* 查看 Tool 调用参数
* 重现生产问题

---

### 🛠 那我可以用 LangSmith 做什么？

#### ✅ 1️⃣ Debug Agent / Workflow（你现在在做）

你正在开发：

👉 背调流程工作流

LangSmith 是：

✨ 最强大的 Debug 面板之一

比：

* 日志
* print
* IDE debug

都更直观



#### ✅ 2️⃣ 记录真实调用日志（生产用）

你可以：

📌 捕获线上每次 LLM 调用
📌 回放
📌 用户投诉可追溯

适合：

✔ SaaS
✔ 金融
✔ 企业应用
✔ 大厂风控合规



#### ✅ 3️⃣ 构建 & 管理 Prompt 版本

包括：

* 历史版本
* 回滚
* diff
* 注释
* label review

很专业。



#### ✅ 4️⃣ 做离线评测（关键价值）

你可以：

📦 定义测试集
⚖ 评估不同模型效果
🧪 做 A/B test
📊 统计准确率/评分

例如：

> 风控分类正确率
> 命中指标
> Hallucination 率
> LLM 自评分

这是你之后做企业级产品必须要的。



#### ✅ 5️⃣ Monitoring（上线后）

你能看到：

📈 成功率
📉 错误分布
⌛ 延迟
💰 成本

甚至：

🔥 哪个 prompt 最贵
🔥 哪个节点最慢

---

### 🧩 结合你的系统，非常适配

你的系统是：

> 公司背景调查 / 风险评估 Pipeline

特点是：

✔ 多阶段
✔ 有状态
✔ LLM + 数据查询
✔ 输出结构 JSON
✔ 需要稳定性

LangSmith 正好提供：

| 需求           | LangSmith 提供 |
| ------------ | ------------ |
| 调试复杂workflow | Graph Trace  |
| 排查问题         | Step Replay  |
| 可观测性         | Monitoring   |
| 评测模型变化影响     | Experiments  |
| 版本管理         | Prompt Store |

非常契合 B2B/合规类系统。

---

### 🤔 你现在可以这样用它

#### 🔹 开发期

👉 在 Studio 里跑 Case：

```
公司 = A
公司 = B
公司 = C
```

逐步完善流程



#### 🔹 测试期

👉 建评测集：

```
公司100家
已知标签：风险/低风险
```

跑LLM对比：

* GPT-4
* DeepSeek
* Claude
* 不同Prompt

输出：

📊 哪个最好
📉 哪个胡说最多



#### 🔹 生产期

👉 接入 tracing client：

```python
langsmith.enable_tracing()
```

得到：

✔ 线上监控
✔ 错误排查
✔ 历史回放

