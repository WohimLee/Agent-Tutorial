## ReAct（Reason + Act
### 🧠 1. ReAct 是什么？

ReAct（Reason + Act）是一种 agent 推理范式，由论文提出，不是软件库。

它的核心思想是让模型交替进行：

- Reasoning（思考）
- Action（动作，例如调用工具）
- Observation（观察工具返回）
- 再继续 Reason → Act → Observation …

>示例结构（ReAct Prompt）：
```py
Thought: 我需要查天气。
Action: weather_api("Beijing")
Observation: 晴天 5℃
Thought: 可以回答了。
Final Answer: 北京今天晴天 5℃
```

➡️ ReAct 本质是一种 Prompting 模式 / 工作方式，不是代码框架。

### 🧩 2. LangGraph 是什么？

LangGraph 是一个用于构建多步骤、带状态、可循环、可分支 AI Agent 的 Python 框架。

它提供：

- 节点（工具 / 模型）
- 状态管理
- 循环与条件分支
- 内存
- Agent workflow 编排

可以让你构建复杂的「智能体流程图」

➡️ LangGraph 是一个真正的软件框架

### 🔄 3. LangGraph 与 ReAct 的关系？
| 项目            | 类型                    | 用途              | 谁更抽象          |
| ------------- | --------------------- | --------------- | ------------- |
| **ReAct**     | 思维链 + Agent 推理策略（方法论） | 控制 LLM 如何思考与行动  | 抽象、轻量，不涉及程序结构 |
| **LangGraph** | Agent 编排框架（代码层面）      | 构建复杂多步工作流 / 状态机 | 更底层的软件框架      |


📌 关系综述

- ReAct 是一种 Agent 的行为模式
- LangGraph 是一个可以实现 ReAct 或其他模式的框架

你可以在 LangGraph 中 实现 ReAct Agent，也可以实现：

- AutoGPT 风格循环
- 中断 / 回溯推理
- 多 Agent 协作
- 工具路由

→ LangGraph 是 ReAct 的 superset（超集）级别工具。

### 🧪 简单例子：在 LangGraph 中实现 ReAct
```py
from langgraph.graph import StateGraph
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-4o")

def react_node(state):
    response = llm.invoke(state["history"])
    state["history"].append(response)
    return state

graph = StateGraph()
graph.add_node("react_step", react_node)
graph.set_entry_point("react_step")
graph.set_finish_point("react_step")

app = graph.compile()
```

➡️ LangGraph 让 ReAct 的循环结构变得正式化、可控化。

### ✅ 总结
LangGraph 和 ReAct 是两个不同的概念：

| 是否框架   | 名称            | 类型                 | 是否软件  |
| ------ | ------------- | ------------------ | ----- |
| ❌ 理论方法 | **ReAct**     | 推理策略（Reason + Act） | 不是软件库 |
| ✔️ 框架  | **LangGraph** | Agent 工作流编排框架      | 是软件库  |


LangGraph 可以实现 ReAct，但 ReAct 本身不是一个完整框架，只是一种 Agent 思维与动作交替的范式。