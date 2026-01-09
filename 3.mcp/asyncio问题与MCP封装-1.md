有，而且还不止一种。你现在这段重复的核心其实是“三件套”：

1. 建立 streamable_http_client
2. 建立 ClientSession
3. initialize()

把这三步抽成一个**可复用的 async context manager**（或一个内部 helper）就行。

下面给你 3 种常用写法，从“最优雅”到“最简单”，你挑一种就能把重复消掉。

---

## 方案 A（最推荐）：用 `@asynccontextmanager` 抽一个 `_session()` 上下文

这样你仍然保持“每次调用即连接、退出即关闭”的语义，但重复代码消失。

```python
from contextlib import asynccontextmanager
from typing import AsyncIterator, Any, Dict, List
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

class MCPClient:
    def __init__(self, mcp_url: str):
        self._mcp_url = mcp_url

    @asynccontextmanager
    async def _session(self) -> AsyncIterator[ClientSession]:
        async with streamable_http_client(self._mcp_url) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session

    async def list_tools_jsons(self) -> List[dict]:
        async with self._session() as session:
            result = await session.list_tools()
            return [tool.model_dump() for tool in result.tools]

    async def list_tools_names(self) -> List[str]:
        async with self._session() as session:
            result = await session.list_tools()
            return [tool.model_dump()["name"] for tool in result.tools]

    async def call_tool(self, name: str, params: Dict[str, Any]) -> str:
        async with self._session() as session:
            resp = await session.call_tool(name, params)
            if resp.content and resp.content[0].type == "text":
                return resp.content[0].text
            return resp.model_dump_json()
```

优点：

* 保留短连接模式
* 代码最清爽
* 你以后加 `timeout / retry / logging / tracing` 都只改 `_session()` 一处

---

## 方案 B：抽一个 `_with_session(fn)` 高阶函数

如果你不喜欢 `asynccontextmanager`，可以用函数式封装：

```python
from typing import Callable, Awaitable, TypeVar
T = TypeVar("T")

class MCPClient:
    def __init__(self, mcp_url: str):
        self._mcp_url = mcp_url

    async def _with_session(self, fn: Callable[[ClientSession], Awaitable[T]]) -> T:
        async with streamable_http_client(self._mcp_url) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return await fn(session)

    async def list_tools_names(self) -> List[str]:
        async def run(session: ClientSession) -> List[str]:
            result = await session.list_tools()
            return [t.model_dump()["name"] for t in result.tools]
        return await self._with_session(run)
```

优点：

* 不用 yield
* 更“函数式”

缺点：

* 写起来略啰嗦（每个方法要写个内部函数/lambda）

---

## 方案 C（更进一步）：做成“长连接”客户端（性能最好）

如果你会在一次流程里频繁调用多个工具（agent loop），短连接每次都 initialize 会慢。

这时可以把连接生命周期上提，让 `MCPClient` 本身支持 `async with`，然后方法里不再重复 session：

```python
class MCPClient:
    def __init__(self, mcp_url: str):
        self._mcp_url = mcp_url
        self._client_cm = None
        self._session = None

    async def __aenter__(self):
        self._client_cm = streamable_http_client(self._mcp_url)
        read, write, _ = await self._client_cm.__aenter__()
        self._session = ClientSession(read, write)
        await self._session.__aenter__()
        await self._session.initialize()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self._session.__aexit__(exc_type, exc, tb)
        await self._client_cm.__aexit__(exc_type, exc, tb)

    async def list_tools_names(self) -> List[str]:
        result = await self._session.list_tools()
        return [t.model_dump()["name"] for t in result.tools]
```

用法：

```python
async with MCPClient(url) as c:
    names = await c.list_tools_names()
    resp = await c.call_tool(...)
```

优点：

* 多次调用工具时速度明显更好（减少重复握手/initialize）
* 调用端写法也很干净

缺点：

* 你要保证“同一个 client 不要被并发共用”（或者自己加锁/建连接池）

---

## 你现在这种场景该选哪个？

* 如果你只是偶尔调用 1~2 次：**方案 A**（最合适）
* 如果你做 agent loop 会调用很多次：**方案 C**（更快）

---

如果你告诉我：你这边一次对话通常会 call_tool 几次（比如 1 次 vs 10 次），我可以直接帮你选定最合适的版本，并顺手把 `list_tools_jsons / list_tools_names` 合并成一次请求避免重复请求（现在你这两个方法各跑一次 `list_tools()`）。
