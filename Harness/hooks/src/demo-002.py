from __future__ import annotations

import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


# ============================================================
# 1. 数据结构
# ============================================================

@dataclass
class Message:
    role: str
    content: str


@dataclass
class ToolCall:
    name: str
    arguments: dict[str, Any]


@dataclass
class ModelResponse:
    """
    模型响应。

    如果 tool_call 不为空，表示模型决定调用工具。
    如果 final_answer 不为空，表示模型决定结束任务。
    """
    tool_call: Optional[ToolCall] = None
    final_answer: Optional[str] = None
    usage: dict[str, int] = field(default_factory=dict)


@dataclass
class AgentState:
    task: str
    messages: list[Message] = field(default_factory=list)
    observations: list[str] = field(default_factory=list)
    final_answer: Optional[str] = None
    step: int = 0
    finished: bool = False


@dataclass
class LLMContext:
    """
    传给模型的结构化上下文。

    Hook 最好修改结构化对象，而不是随意拼接字符串。
    """
    system_prompt: str
    messages: list[Message]
    memories: list[str] = field(default_factory=list)
    tool_descriptions: list[str] = field(default_factory=list)


@dataclass
class ToolContext:
    """
    工具调用相关上下文。

    before_tool 和 after_tool Hook 都会接收到它。
    """
    state: AgentState
    tool_call: ToolCall
    result: Any = None
    error: Optional[Exception] = None


# ============================================================
# 2. Hook 系统
# ============================================================

HookHandler = Callable[[Any], Any]


class HookManager:
    """
    一个简单的 Hook 管理器。

    支持两种触发方式：

    1. emit:
       仅通知所有 Hook，不关心返回值。

    2. transform:
       前一个 Hook 的返回值，会传递给后一个 Hook。
       适合修改 Prompt、上下文等数据。
    """

    def __init__(self) -> None:
        self._hooks: dict[str, list[tuple[int, HookHandler]]] = defaultdict(list)

    def register(
        self,
        hook_name: str,
        handler: HookHandler,
        priority: int = 100,
    ) -> None:
        """
        注册 Hook。

        priority 越小，越早执行。
        """
        self._hooks[hook_name].append((priority, handler))
        self._hooks[hook_name].sort(key=lambda item: item[0])

    def unregister(
        self,
        hook_name: str,
        handler: HookHandler,
    ) -> None:
        handlers = self._hooks.get(hook_name, [])
        self._hooks[hook_name] = [
            item for item in handlers if item[1] is not handler
        ]

    def emit(self, hook_name: str, payload: Any) -> None:
        """
        广播事件。

        Hook 的返回值会被忽略。
        """
        for _, handler in self._hooks.get(hook_name, []):
            handler(payload)

    def transform(self, hook_name: str, value: Any) -> Any:
        """
        链式修改数据。

        每个 Hook 可以：
        - 返回修改后的值
        - 返回 None，表示不修改
        """
        current = value

        for _, handler in self._hooks.get(hook_name, []):
            result = handler(current)

            if result is not None:
                current = result

        return current


# ============================================================
# 3. Tool 系统
# ============================================================

ToolFunction = Callable[..., Any]


@dataclass
class Tool:
    name: str
    description: str
    function: ToolFunction

    def execute(self, arguments: dict[str, Any]) -> Any:
        return self.function(**arguments)


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(
        self,
        name: str,
        description: str,
        function: ToolFunction,
    ) -> None:
        if name in self._tools:
            raise ValueError(f"工具已经注册：{name}")

        self._tools[name] = Tool(
            name=name,
            description=description,
            function=function,
        )

    def get(self, name: str) -> Tool:
        tool = self._tools.get(name)

        if tool is None:
            raise KeyError(f"未知工具：{name}")

        return tool

    def descriptions(self) -> list[str]:
        return [
            f"{tool.name}: {tool.description}"
            for tool in self._tools.values()
        ]


# ============================================================
# 4. 简单记忆系统
# ============================================================

class MemoryStore:
    def __init__(self) -> None:
        self._items: list[str] = []

    def add(self, item: str) -> None:
        self._items.append(item)

    def search(self, query: str, limit: int = 3) -> list[str]:
        """
        为了让示例不依赖向量数据库，这里用最简单的关键词匹配。
        """
        query_words = set(query.lower().split())

        scored_items: list[tuple[int, str]] = []

        for item in self._items:
            item_words = set(item.lower().split())
            score = len(query_words & item_words)
            scored_items.append((score, item))

        scored_items.sort(key=lambda item: item[0], reverse=True)

        return [
            item
            for score, item in scored_items[:limit]
            if score > 0
        ]


# ============================================================
# 5. 模型接口
# ============================================================

class BaseModel:
    def generate(self, context: LLMContext) -> ModelResponse:
        raise NotImplementedError


class MockModel(BaseModel):
    """
    模拟 LLM。

    目的是演示 Agent、Tool 和 Hook 的协作方式，
    不需要连接真实模型。

    规则：
    - 第一次看到加法任务时，调用 calculator 工具。
    - 得到工具结果后，输出最终答案。
    """

    def generate(self, context: LLMContext) -> ModelResponse:
        last_message = context.messages[-1].content

        # 发现工具结果后，生成最终答案
        if last_message.startswith("工具执行结果："):
            result = last_message.removeprefix("工具执行结果：").strip()

            return ModelResponse(
                final_answer=f"计算完成，结果是：{result}",
                usage={
                    "prompt_tokens": 80,
                    "completion_tokens": 15,
                },
            )

        # 模拟模型判断：需要调用计算器
        if "加" in last_message or "+" in last_message:
            numbers = self._extract_numbers(last_message)

            if len(numbers) >= 2:
                return ModelResponse(
                    tool_call=ToolCall(
                        name="calculator",
                        arguments={
                            "a": numbers[0],
                            "b": numbers[1],
                        },
                    ),
                    usage={
                        "prompt_tokens": 60,
                        "completion_tokens": 12,
                    },
                )

        return ModelResponse(
            final_answer="我暂时无法处理这个任务。",
            usage={
                "prompt_tokens": 40,
                "completion_tokens": 10,
            },
        )

    @staticmethod
    def _extract_numbers(text: str) -> list[float]:
        numbers: list[float] = []
        current = ""

        for char in text:
            if char.isdigit() or char == ".":
                current += char
            elif current:
                numbers.append(float(current))
                current = ""

        if current:
            numbers.append(float(current))

        return numbers


# ============================================================
# 6. Agent 核心
# ============================================================

class Agent:
    """
    Agent 核心主循环。

    这里显式保留核心步骤：

    1. 构建上下文
    2. 调用模型
    3. 解析模型结果
    4. 调用工具
    5. 更新状态
    6. 判断是否结束

    日志、记忆、权限、统计等附加功能由 Hook 处理。
    """

    def __init__(
        self,
        model: BaseModel,
        tools: ToolRegistry,
        memory: MemoryStore,
        hooks: Optional[HookManager] = None,
        max_steps: int = 5,
    ) -> None:
        self.model = model
        self.tools = tools
        self.memory = memory
        self.hooks = hooks or HookManager()
        self.max_steps = max_steps

    def run(self, task: str) -> str:
        state = AgentState(task=task)
        state.messages.append(Message(role="user", content=task))

        self.hooks.emit("agent_start", state)

        try:
            while not state.finished:
                if state.step >= self.max_steps:
                    state.final_answer = "达到最大执行步数，任务终止。"
                    state.finished = True
                    break

                state.step += 1
                self.hooks.emit("step_start", state)

                # ----------------------------
                # 核心步骤 1：构建模型上下文
                # ----------------------------
                context = self._build_context(state)

                # Hook 可以注入记忆、策略、额外信息
                context = self.hooks.transform(
                    "before_llm",
                    context,
                )

                # ----------------------------
                # 核心步骤 2：调用模型
                # ----------------------------
                started_at = time.perf_counter()

                try:
                    response = self.model.generate(context)
                except Exception as exc:
                    self.hooks.emit(
                        "llm_error",
                        {
                            "state": state,
                            "error": exc,
                        },
                    )
                    raise

                elapsed = time.perf_counter() - started_at

                self.hooks.emit(
                    "after_llm",
                    {
                        "state": state,
                        "response": response,
                        "elapsed": elapsed,
                    },
                )

                # ----------------------------
                # 核心步骤 3：处理模型决策
                # ----------------------------
                if response.final_answer is not None:
                    state.final_answer = response.final_answer
                    state.finished = True
                    break

                if response.tool_call is not None:
                    result = self._execute_tool(
                        state=state,
                        tool_call=response.tool_call,
                    )

                    state.observations.append(str(result))
                    state.messages.append(
                        Message(
                            role="tool",
                            content=f"工具执行结果：{result}",
                        )
                    )

                    self.hooks.emit(
                        "state_updated",
                        state,
                    )
                    continue

                raise RuntimeError("模型既没有返回工具调用，也没有返回答案。")

        except Exception as exc:
            self.hooks.emit(
                "agent_error",
                {
                    "state": state,
                    "error": exc,
                },
            )

            state.final_answer = f"Agent 执行失败：{exc}"
            state.finished = True

        finally:
            self.hooks.emit("agent_finish", state)

        return state.final_answer or "没有生成答案。"

    def _build_context(self, state: AgentState) -> LLMContext:
        return LLMContext(
            system_prompt=(
                "你是一个能够使用工具解决问题的助手。"
                "需要计算时，请调用 calculator 工具。"
            ),
            messages=list(state.messages),
            memories=[],
            tool_descriptions=self.tools.descriptions(),
        )

    def _execute_tool(
        self,
        state: AgentState,
        tool_call: ToolCall,
    ) -> Any:
        tool_context = ToolContext(
            state=state,
            tool_call=tool_call,
        )

        # before_tool 可以做权限检查、参数修改、审计等
        tool_context = self.hooks.transform(
            "before_tool",
            tool_context,
        )

        tool = self.tools.get(tool_context.tool_call.name)

        started_at = time.perf_counter()

        try:
            result = tool.execute(
                tool_context.tool_call.arguments
            )
            tool_context.result = result

        except Exception as exc:
            tool_context.error = exc
            self.hooks.emit("tool_error", tool_context)
            raise

        finally:
            elapsed = time.perf_counter() - started_at

            self.hooks.emit(
                "after_tool",
                {
                    "context": tool_context,
                    "elapsed": elapsed,
                },
            )

        return tool_context.result


# ============================================================
# 7. 插件
# ============================================================

class LoggingPlugin:
    """
    日志插件。

    通过 Hook 接入 Agent，不修改 Agent 主循环。
    """

    def register(self, hooks: HookManager) -> None:
        hooks.register(
            "agent_start",
            self.on_agent_start,
        )
        hooks.register(
            "step_start",
            self.on_step_start,
        )
        hooks.register(
            "after_llm",
            self.on_after_llm,
        )
        hooks.register(
            "before_tool",
            self.on_before_tool,
        )
        hooks.register(
            "after_tool",
            self.on_after_tool,
        )
        hooks.register(
            "agent_finish",
            self.on_agent_finish,
        )

    def on_agent_start(self, state: AgentState) -> None:
        print(f"\n[Agent] 开始任务：{state.task}")

    def on_step_start(self, state: AgentState) -> None:
        print(f"\n[Agent] 第 {state.step} 步")

    def on_after_llm(self, payload: dict[str, Any]) -> None:
        response: ModelResponse = payload["response"]
        elapsed: float = payload["elapsed"]

        if response.tool_call:
            print(
                "[LLM] 决定调用工具："
                f"{response.tool_call.name}"
            )
        else:
            print("[LLM] 决定输出最终答案")

        print(f"[LLM] 耗时：{elapsed:.6f} 秒")

    def on_before_tool(
        self,
        context: ToolContext,
    ) -> ToolContext:
        print(
            "[Tool] 即将调用："
            f"{context.tool_call.name} "
            f"{context.tool_call.arguments}"
        )
        return context

    def on_after_tool(self, payload: dict[str, Any]) -> None:
        context: ToolContext = payload["context"]
        elapsed: float = payload["elapsed"]

        if context.error:
            print(f"[Tool] 调用失败：{context.error}")
        else:
            print(f"[Tool] 调用结果：{context.result}")

        print(f"[Tool] 耗时：{elapsed:.6f} 秒")

    def on_agent_finish(self, state: AgentState) -> None:
        print(f"\n[Agent] 任务结束：{state.final_answer}")


class MemoryPlugin:
    """
    记忆插件。

    在调用 LLM 前检索记忆并注入上下文；
    Agent 完成后，将任务和答案保存到记忆。
    """

    def __init__(self, memory: MemoryStore) -> None:
        self.memory = memory

    def register(self, hooks: HookManager) -> None:
        hooks.register(
            "before_llm",
            self.inject_memory,
            priority=50,
        )
        hooks.register(
            "agent_finish",
            self.save_memory,
        )

    def inject_memory(self, context: LLMContext) -> LLMContext:
        if not context.messages:
            return context

        query = context.messages[-1].content
        memories = self.memory.search(query)

        context.memories.extend(memories)

        if memories:
            print(f"[Memory] 注入记忆：{memories}")
        else:
            print("[Memory] 没有找到相关记忆")

        return context

    def save_memory(self, state: AgentState) -> None:
        if state.final_answer:
            item = (
                f"任务：{state.task}；"
                f"答案：{state.final_answer}"
            )
            self.memory.add(item)
            print("[Memory] 已保存本次任务")


class SecurityPlugin:
    """
    安全插件。

    在工具执行前检查工具白名单和参数。
    """

    def __init__(self, allowed_tools: set[str]) -> None:
        self.allowed_tools = allowed_tools

    def register(self, hooks: HookManager) -> None:
        hooks.register(
            "before_tool",
            self.check_tool,
            priority=10,
        )

    def check_tool(
        self,
        context: ToolContext,
    ) -> ToolContext:
        tool_call = context.tool_call

        if tool_call.name not in self.allowed_tools:
            raise PermissionError(
                f"工具不在白名单中：{tool_call.name}"
            )

        if tool_call.name == "calculator":
            arguments = tool_call.arguments

            if "a" not in arguments or "b" not in arguments:
                raise ValueError("calculator 缺少参数 a 或 b")

            for name in ("a", "b"):
                value = arguments[name]

                if not isinstance(value, (int, float)):
                    raise TypeError(
                        f"参数 {name} 必须是数字"
                    )

                if abs(value) > 1_000_000:
                    raise ValueError(
                        f"参数 {name} 超出允许范围"
                    )

        print("[Security] 工具调用检查通过")
        return context


class MetricsPlugin:
    """
    指标统计插件。

    统计：
    - LLM 调用次数
    - 工具调用次数
    - Token 用量
    - 总耗时
    """

    def __init__(self) -> None:
        self.agent_started_at = 0.0
        self.llm_calls = 0
        self.tool_calls = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0

    def register(self, hooks: HookManager) -> None:
        hooks.register(
            "agent_start",
            self.on_agent_start,
        )
        hooks.register(
            "after_llm",
            self.on_after_llm,
        )
        hooks.register(
            "after_tool",
            self.on_after_tool,
        )
        hooks.register(
            "agent_finish",
            self.on_agent_finish,
        )

    def on_agent_start(self, state: AgentState) -> None:
        self.agent_started_at = time.perf_counter()

    def on_after_llm(self, payload: dict[str, Any]) -> None:
        response: ModelResponse = payload["response"]

        self.llm_calls += 1
        self.prompt_tokens += response.usage.get(
            "prompt_tokens",
            0,
        )
        self.completion_tokens += response.usage.get(
            "completion_tokens",
            0,
        )

    def on_after_tool(self, payload: dict[str, Any]) -> None:
        self.tool_calls += 1

    def on_agent_finish(self, state: AgentState) -> None:
        total_elapsed = (
            time.perf_counter() - self.agent_started_at
        )

        print("\n[Metrics]")
        print(f"LLM 调用次数：{self.llm_calls}")
        print(f"工具调用次数：{self.tool_calls}")
        print(f"输入 Token：{self.prompt_tokens}")
        print(f"输出 Token：{self.completion_tokens}")
        print(f"总耗时：{total_elapsed:.6f} 秒")


class PromptPolicyPlugin:
    """
    Prompt 策略插件。

    演示如何在 before_llm Hook 中修改结构化上下文。
    """

    def register(self, hooks: HookManager) -> None:
        hooks.register(
            "before_llm",
            self.add_policy,
            priority=20,
        )

    def add_policy(self, context: LLMContext) -> LLMContext:
        context.system_prompt += (
            "\n回答必须简洁。"
            "\n不得编造工具执行结果。"
        )

        return context


# ============================================================
# 8. 工具函数
# ============================================================

def calculator(a: float, b: float) -> float:
    return a + b


def dangerous_delete_file(path: str) -> str:
    """
    只是演示，不会真的删除文件。
    """
    return f"已删除文件：{path}"


# ============================================================
# 9. 组装并运行
# ============================================================

def build_agent() -> Agent:
    hooks = HookManager()
    tools = ToolRegistry()
    memory = MemoryStore()

    # 注册工具
    tools.register(
        name="calculator",
        description="计算两个数字之和，参数为 a 和 b。",
        function=calculator,
    )

    tools.register(
        name="delete_file",
        description="删除指定文件。",
        function=dangerous_delete_file,
    )

    # 注册插件
    LoggingPlugin().register(hooks)
    MemoryPlugin(memory).register(hooks)
    SecurityPlugin(
        allowed_tools={"calculator"}
    ).register(hooks)
    MetricsPlugin().register(hooks)
    PromptPolicyPlugin().register(hooks)

    # 创建 Agent
    return Agent(
        model=MockModel(),
        tools=tools,
        memory=memory,
        hooks=hooks,
        max_steps=5,
    )


if __name__ == "__main__":
    agent = build_agent()

    answer = agent.run("请帮我计算 15 加 27")

    print("\n最终返回值：")
    print(answer)