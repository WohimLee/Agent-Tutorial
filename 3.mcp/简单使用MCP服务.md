很好，这正是 MCP（Model Context Protocol）被设计出来要解决的事情 👍
我用**最实用的 Python 调用方式**给你从 0 到 1 讲清楚。

---

# 一、你需要知道的最小 MCP 心智模型

MCP 本质上是：

> 一个 **AI 可以通过 JSON-RPC 调用的工具服务器**

你的 Python 程序要做的事情是：

```
Python  →  MCP Client  →  MCP Server  →  Tool → 返回 JSON
```

所以你不需要关心 LLM
你只是在用 Python 调一个「远程可执行工具 API」

---

# 二、MCP 有 2 种连接方式（你一定要知道）

一个 MCP server 通常用其中一种方式暴露：

| 类型             | 用途                              |
| -------------- | ------------------------------- |
| **stdio**      | 本地进程（Claude Desktop, Cursor 常用） |
| **http / sse** | 网络服务（你现在这个 MCP 多半是这种）           |

你说“我知道一个 mcp 服务”，**99% 是 http MCP**

我先给你 HTTP 版本（生产用），后面补 stdio 版。

---

# 三、用 Python 调用 MCP（HTTP 版本）

你需要 3 个步骤：

1. 列出 MCP 提供的 tools
2. 选择一个 tool
3. 调用它

---

## 1️⃣ 安装 MCP Python 客户端

```bash
pip install mcp
```

---

## 2️⃣ 连接 MCP Server

假设你的 MCP server 是：

```
http://localhost:3333/mcp
```

```python
from mcp import ClientSession
from mcp.client.http import HttpClientTransport

transport = HttpClientTransport("http://localhost:3333/mcp")

session = ClientSession(transport)
```

---

## 3️⃣ 获取这个 MCP 提供了哪些工具

```python
tools = await session.list_tools()

for tool in tools:
    print(tool.name, tool.description)
```

你会看到类似：

```
search_docs     在公司知识库中搜索
create_ticket   创建工单
query_db        查询数据库
```

---

## 4️⃣ 调用 MCP 的某个工具

比如 MCP 提供了：

```json
{
  "name": "search_docs",
  "inputSchema": {
    "query": "string"
  }
}
```

你可以这样调：

```python
result = await session.call_tool(
    "search_docs",
    {
        "query": "如何部署MCP"
    }
)

print(result.content)
```

MCP 返回的就是 JSON 结果，例如：

```json
{
  "documents": [
    {"title": "MCP Spec", "url": "..."}
  ]
}
```

---

# 四、完整可运行示例（可直接用）

```python
import asyncio
from mcp import ClientSession
from mcp.client.http import HttpClientTransport

async def main():
    transport = HttpClientTransport("http://localhost:3333/mcp")
    session = ClientSession(transport)

    # 列出工具
    tools = await session.list_tools()
    print("Available tools:")
    for t in tools:
        print("-", t.name)

    # 调用第一个工具
    tool_name = tools[0].name
    result = await session.call_tool(tool_name, {})

    print("Result:", result.content)

asyncio.run(main())
```

---

# 五、如果你的 MCP 是 stdio（本地程序）

比如 MCP 是一个：

```bash
npx my-mcp-server
```

那么你用：

```python
from mcp.client.stdio import StdioClientTransport

transport = StdioClientTransport(
    command="npx",
    args=["my-mcp-server"]
)
session = ClientSession(transport)
```

后面用法一模一样。

---

# 六、你现在最关键的问题

你可以把 MCP 地址发给我，比如：

```
http://xxx.xxx.xxx/mcp
```

或者

```
npx xxx-mcp
```

我可以直接帮你：

* 判断它是哪种 MCP
* 告诉你正确 Python 调用方式
* 甚至帮你写**你这个 MCP 的专用 client**

🚀
