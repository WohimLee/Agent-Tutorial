## mcp & fastmcp
>一句话总结
- mcp 是官方、底层、偏协议的实现；fastmcp 是在 mcp 之上做的高层封装，更像 FastAPI 之于 Starlette。

>核心区别对照表

| 维度    | `mcp`                  | `fastmcp`        |
| ----- | ---------------------- | ---------------- |
| 抽象层级  | **低层**（协议级）            | **高层**（框架级）      |
| 官方性   | 官方 SDK / 参考实现          | 社区或官方实验性高层封装     |
| 使用复杂度 | 偏复杂                    | 非常简单             |
| 编程风格  | 偏“协议 & 事件”             | **声明式 / 装饰器风格**  |
| 适合人群  | 框架作者、深度定制              | **应用开发者**        |
| 类比    | Starlette / ASGI       | **FastAPI**      |
| 主要用途  | 实现 MCP Server / Client | 快速写 MCP 工具、资源、提示 |


### 1 mcp：底层、完整、偏协议
##### 它是什么？
- Model Context Protocol 的官方 Python 实现

- 提供：
    - MCP Server / Client
    - Transport（stdio、http、websocket）
    - 消息、能力协商、生命周期

- 非常贴近协议本身

##### 使用特点

你需要：
- 手动注册 tools / resources
- 自己处理上下文、schema、序列化
- 自由度极高，但样板代码多

##### 适合谁？

- 想自己封装一套 MCP 框架
- 想深入控制协议行为
- 想实现非标准或实验性 MCP 功能

>示例（风格示意）
```py
from mcp.server import Server
from mcp.types import Tool

server = Server("demo")

server.add_tool(
    Tool(
        name="add",
        description="Add two numbers",
        input_schema={...},
        handler=add_handler,
    )
)
```

👉 更像“搭积木”

### 2 fastmcp：高层、易用、偏应用
##### 它是什么？

- 基于 mcp 的高层封装
- 目标：让你 5 分钟写完一个 MCP Server
- API 设计明显受 FastAPI 启发

##### 使用特点

- 使用：
    - 装饰器
    - 自动 schema 推导
    - 自动注册 tools / resources / prompts
- 几乎不需要关心协议细节

##### 适合谁？

- 绝大多数 MCP 工具 / Agent 开发者
- 想快速把 Python 函数暴露给 LLM
- 写插件、工具服务器、Agent 后端

>示例（风格示意）
```py
from fastmcp import FastMCP

mcp = FastMCP("demo")

@mcp.tool()
def add(a: int, b: int) -> int:
    return a + b
```

👉 更像“写业务代码”

### 3 功能覆盖关系
```
┌──────────────────────────┐
│        fastmcp           │  ← 高层、易用
│  (decorators, auto schema│
│   tools/resources)       │
└──────────▲───────────────┘
           │ 基于
┌──────────┴───────────────┐
│            mcp           │  ← 底层、完整
│ (protocol, transport,    │
│  server/client core)     │
└──────────────────────────┘
```
### 4 该选哪个？
##### 👉 选 fastmcp，如果你：

- 只是想：
    - 写 MCP 工具
    - 接入 Claude / GPT / Agent
    - 不想关心协议细节
    - 熟悉 FastAPI 风格

- ✔ 90% 的应用场景

##### 👉 选 mcp，如果你：

- 要：
    - 实现自定义 MCP 框架
    - 深度定制 transport / 生命周期
    - 或在做 SDK / 平台级工作
- ✔ 10% 的底层 / 平台场景

简单类比（很好记）
| Web 世界           | MCP 世界        |
| ---------------- | ------------- |
| ASGI / Starlette | `mcp`         |
| **FastAPI**      | **`fastmcp`** |
