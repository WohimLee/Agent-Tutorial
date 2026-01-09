下面给你一个“**一问一连接**”的 ShadowHunter agent 最佳实践模板：
目标是 **每次用户 query 打开一次 MCP 连接**，在 agent loop 里复用同一条 session；query 结束就自动关闭。这样最快、最稳，也最容易排查问题。

我给你一套可以直接抄进项目的结构（3 个层次）：

* `MCPClient`：长连接（方案 C）+ 提供 `list_tools/call_tool`
* `MCPToolProvider`：把 MCP 工具一次性发现并缓存到本次 run（避免重复 list_tools）
* `ShadowHunterAgent`：每次 `answer(question)` 都自己管理 `async with MCPClient(...)` 生命周期（**一问一连接**）

---

## 1) 长连接版 MCPClient（可复用、支持 async with）

```python
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client


class MCPClient:
    """
    长连接 MCP Client：在 async with 作用域内复用同一条 session。
    适合 agent loop（多次 call_tool）。
    """

    def __init__(self, mcp_url: str):
        self._mcp_url = mcp_url
        self._http_cm = None
        self._session: Optional[ClientSession] = None

    async def __aenter__(self) -> "MCPClient":
        # 注意：这里我们手动驱动底层 context manager
        self._http_cm = streamable_http_client(self._mcp_url)
        read, write, _ = await self._http_cm.__aenter__()

        self._session = ClientSession(read, write)
        await self._session.__aenter__()
        await self._session.initialize()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        # 先关 session 再关 http client
        if self._session is not None:
            await self._session.__aexit__(exc_type, exc, tb)
            self._session = None
        if self._http_cm is not None:
            await self._http_cm.__aexit__(exc_type, exc, tb)
            self._http_cm = None

    @property
    def session(self) -> ClientSession:
        if self._session is None:
            raise RuntimeError("MCPClient not entered. Use `async with MCPClient(...)`.")
        return self._session

    async def list_tools(self) -> List[dict]:
        result = await self.session.list_tools()
        return [t.model_dump() for t in result.tools]  # type: ignore

    async def call_tool(self, name: str, params: Dict[str, Any]) -> str:
        resp = await self.session.call_tool(name, params)
        if resp.content and resp.content[0].type == "text":
            return resp.content[0].text
        return resp.model_dump_json()
```

---

## 2) 本次对话工具发现与转换（一次发现、一次缓存）

避免你在 agent 里重复 `list_tools()`，并且把 MCP 的 schema 转成 LLM tools schema（OpenAI / DashScope 兼容格式）。

```python
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


def mcp_tool_to_openai_schema(t: dict) -> Tuple[dict, Optional[dict]]:
    """
    MCP tool -> OpenAI tools schema
    返回：(openai_tool_schema, input_schema)
    """
    name = t["name"]
    desc = t.get("description", "")
    schema = t.get("inputSchema") or {"type": "object", "properties": {}, "required": []}

    openai_tool = {
        "type": "function",
        "function": {
            "name": name,
            "description": desc,
            "parameters": schema,
        },
    }
    return openai_tool, schema


class MCPToolProvider:
    """
    一次 run 内缓存工具列表，避免重复 list_tools。
    """

    def __init__(self):
        self._openai_tools: List[dict] = []
        self._schemas: Dict[str, Optional[dict]] = {}

    @property
    def openai_tools(self) -> List[dict]:
        return self._openai_tools

    @property
    def schemas(self) -> Dict[str, Optional[dict]]:
        return self._schemas

    async def bootstrap(self, mcp: "MCPClient") -> None:
        raw = await mcp.list_tools()
        self._openai_tools = []
        self._schemas = {}

        for t in raw:
            openai_tool, schema = mcp_tool_to_openai_schema(t)
            name = openai_tool["function"]["name"]
            self._openai_tools.append(openai_tool)
            self._schemas[name] = schema
```

---

## 3) ShadowHunterAgent：一问一连接（核心最佳实践）

关键点：

* `answer(question)` 内部 `async with MCPClient(...)`
* 同一个 question 的多轮工具调用全部复用同一 session
* 工具发现也在同一次连接里做（只做一次）
* 工具调用失败要“返回给 LLM”而不是直接 raise（否则对话会断）

下面以 DashScope(OpenAI-compatible) 的 client 风格举例，你也可以替换成你自己的 LLM wrapper：

```python
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from openai import OpenAI


class ShadowHunterAgent:
    def __init__(
        self,
        llm_api_key: str,
        llm_base_url: str,
        model: str,
        mcp_url: str,
        max_tool_calls: int = 10,
    ):
        self._llm = OpenAI(api_key=llm_api_key, base_url=llm_base_url)
        self._model = model
        self._mcp_url = mcp_url
        self._max_tool_calls = max_tool_calls

    def _system_prompt(self, tools: List[dict]) -> str:
        if not tools:
            return "你是 ShadowHunter 智能助手。当前没有可用工具，请基于已知知识回答。"
        brief = "\n".join(
            f"- {t['function']['name']}: {t['function'].get('description','')}"
            for t in tools
        )
        return (
            "你是 ShadowHunter 智能助手。你可以调用以下工具：\n"
            f"{brief}\n\n"
            "当需要实时/外部信息时使用工具；否则直接回答。"
        )

    async def answer(self, user_query: str) -> str:
        tool_provider = MCPToolProvider()

        # ✅ 一问一连接：对这一个问题，打开一次 MCP 连接，直到结束自动关闭
        async with MCPClient(self._mcp_url) as mcp:
            # 只在本次 run 里 bootstrap 一次工具
            await tool_provider.bootstrap(mcp)

            messages: List[Dict[str, Any]] = [
                {"role": "system", "content": self._system_prompt(tool_provider.openai_tools)},
                {"role": "user", "content": user_query},
            ]

            for attempt in range(self._max_tool_calls + 1):
                resp = self._llm.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    tools=tool_provider.openai_tools if attempt < self._max_tool_calls else None,
                    temperature=0.35,
                )

                msg = resp.choices[0].message
                tool_calls = msg.tool_calls or []

                # 不需要工具 => 直接结束
                if not tool_calls:
                    return msg.content or "（空响应）"

                # 追加 assistant 工具调用请求
                messages.append(
                    {
                        "role": "assistant",
                        "content": msg.content or "",
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments,
                                },
                            }
                            for tc in tool_calls
                        ],
                    }
                )

                # 逐个执行工具调用（同一个 mcp session 复用）
                for tc in tool_calls:
                    name = tc.function.name
                    try:
                        args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                    except json.JSONDecodeError:
                        args = {}

                    try:
                        tool_out = await mcp.call_tool(name, args)
                    except Exception as e:  # noqa: BLE001
                        # ✅ 不要 raise，让 LLM 看到错误并决定如何继续
                        tool_out = f"工具调用失败：{type(e).__name__}: {e}"

                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": tool_out,
                        }
                    )

            return "已达到最大工具调用次数，建议你缩小问题范围或换一种问法。"
```

---

## 你在 ShadowHunter 项目里怎么落地（最小改动）

你原来可能是这种（短连接）：

```python
client = MCPClient(url)
# agent 里每次 call_tool 又重新开连接
```

现在改成：

* 把 agent 的入口统一成 `await agent.answer(query)`
* `answer()` 内部使用 `async with MCPClient(...)`
* 把 `mcp_url` 或者 `tavily_url` 在 agent 初始化时传入

示例：

```python
agent = ShadowHunterAgent(
    llm_api_key=settings.dashscope_api_key,
    llm_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    model="qwen-plus",
    mcp_url=f"https://mcp.tavily.com/mcp/?tavilyApiKey={settings.tavily_api_key}",
)

reply = await agent.answer("帮我查一下最近的……")
print(reply)
```

---

## 额外的“最佳实践”小提醒（很重要）

1. **不要把一个 MCPClient 长期存成全局单例**给所有请求共用

   * 并发会乱序/串台（尤其 agent 并发）

2. 如果你要支持并发（多个用户同时问）

   * 每个请求各自 `async with MCPClient(...)`（一问一连接）就天然隔离了

3. 你原来 `list_tools_jsons()` 和 `list_tools_names()` 会各自打一次 `list_tools()`

   * 现在 bootstrap 一次后可以从缓存里派生 names/json（避免重复网络请求）

---

如果你把 ShadowHunter 里负责“agent loop + tool router”的那段文件（比如 `shadowhunter/agent/...` 或 `mcp_tools.py`）贴出来，我可以按你现有项目结构把以上模板“原地改造”，做到：**改动行数最少、接口不破坏、日志/异常风格保持一致**。
