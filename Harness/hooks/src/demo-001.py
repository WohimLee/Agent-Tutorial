from __future__ import annotations

import time
import json
import hashlib
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


HookFn = Callable[["Context"], None]


@dataclass
class Context:
    user_input: str
    normalized_input: str = ""
    query: str = ""
    docs: List[Dict[str, Any]] = field(default_factory=list)
    prompt: str = ""
    llm_output: str = ""
    parsed: Dict[str, Any] = field(default_factory=dict)
    tool_name: Optional[str] = None
    tool_args: Dict[str, Any] = field(default_factory=dict)
    tool_result: Any = None
    final_response: str = ""
    error: Optional[Exception] = None
    stage: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class HookManager:
    def __init__(self):
        self.hooks: Dict[str, List[tuple[int, HookFn]]] = {}

    def register(self, name: str, fn: HookFn, priority: int = 100):
        self.hooks.setdefault(name, []).append((priority, fn))
        self.hooks[name].sort(key=lambda x: x[0])

    def emit(self, name: str, ctx: Context):
        for _, fn in self.hooks.get(name, []):
            fn(ctx)


class Cache:
    def __init__(self):
        self.store: Dict[str, str] = {}

    def key(self, text: str) -> str:
        return hashlib.md5(text.encode("utf-8")).hexdigest()

    def get(self, text: str) -> Optional[str]:
        return self.store.get(self.key(text))

    def set(self, text: str, value: str):
        self.store[self.key(text)] = value


class FakeRetriever:
    def retrieve(self, query: str) -> List[Dict[str, Any]]:
        docs = [
            {"text": "Hook 是生命周期中的扩展点。", "score": 0.95},
            {"text": "Agent 可以在调用 LLM 前后使用 hook。", "score": 0.9},
            {"text": "Tool hook 可用于权限检查、日志、重试。", "score": 0.86},
            {"text": "无关文档", "score": 0.3},
        ]
        return docs


class FakeLLM:
    def generate(self, prompt: str) -> str:
        if "计算" in prompt or "calculator" in prompt:
            return json.dumps({
                "type": "tool_call",
                "tool": "calculator",
                "args": {"expression": "1 + 2 * 3"}
            }, ensure_ascii=False)

        return json.dumps({
            "type": "final",
            "answer": "Hook 是 Agent 生命周期中的扩展点，可用于日志、缓存、安全检查、RAG 改写、工具审计等。"
        }, ensure_ascii=False)

    def stream(self, text: str):
        for ch in text:
            time.sleep(0.01)
            yield ch


class Tools:
    @staticmethod
    def calculator(expression: str) -> Any:
        allowed = set("0123456789+-*/(). ")
        if not set(expression) <= allowed:
            raise ValueError("Unsafe expression")
        return eval(expression, {"__builtins__": {}})

    @staticmethod
    def search(query: str) -> str:
        return f"搜索结果：{query}"


class Agent:
    def __init__(self):
        self.hooks = HookManager()
        self.cache = Cache()
        self.retriever = FakeRetriever()
        self.llm = FakeLLM()
        self.tools = {
            "calculator": Tools.calculator,
            "search": Tools.search,
        }

    def run(self, user_input: str, stream: bool = False) -> str:
        ctx = Context(user_input=user_input)

        try:
            self.hooks.emit("on_start", ctx)

            ctx.stage = "input"
            self.hooks.emit("pre_input", ctx)
            ctx.normalized_input = user_input.strip()
            self.hooks.emit("post_input", ctx)

            ctx.stage = "memory"
            self.hooks.emit("pre_memory", ctx)
            ctx.metadata["memory"] = "用户偏好：喜欢 Python 示例。"
            self.hooks.emit("post_memory", ctx)

            ctx.stage = "retrieval"
            self.hooks.emit("pre_retrieval", ctx)
            ctx.query = ctx.normalized_input
            ctx.docs = self.retriever.retrieve(ctx.query)
            self.hooks.emit("post_retrieval", ctx)

            ctx.stage = "rerank"
            self.hooks.emit("pre_rerank", ctx)
            ctx.docs = sorted(ctx.docs, key=lambda d: d["score"], reverse=True)
            self.hooks.emit("post_rerank", ctx)

            ctx.stage = "prompt"
            self.hooks.emit("pre_prompt", ctx)
            context_text = "\n".join(d["text"] for d in ctx.docs)
            ctx.prompt = f"""
你是一个 LLM Agent。

用户问题：
{ctx.normalized_input}

记忆：
{ctx.metadata.get("memory", "")}

检索上下文：
{context_text}

请用 JSON 输出：
- 如果需要工具，输出 {{"type":"tool_call","tool":"工具名","args":{{...}}}}
- 如果不需要工具，输出 {{"type":"final","answer":"..."}}
"""
            self.hooks.emit("post_prompt", ctx)

            ctx.stage = "cache"
            self.hooks.emit("pre_cache", ctx)
            cached = self.cache.get(ctx.prompt)
            self.hooks.emit("post_cache", ctx)

            if cached:
                ctx.llm_output = cached
            else:
                ctx.stage = "llm"
                self.hooks.emit("pre_llm", ctx)
                ctx.llm_output = self._call_llm_with_retry(ctx)
                self.cache.set(ctx.prompt, ctx.llm_output)
                self.hooks.emit("post_llm", ctx)

            ctx.stage = "parse"
            self.hooks.emit("pre_parse", ctx)
            ctx.parsed = json.loads(ctx.llm_output)
            self.hooks.emit("post_parse", ctx)

            if ctx.parsed.get("type") == "tool_call":
                ctx.tool_name = ctx.parsed["tool"]
                ctx.tool_args = ctx.parsed.get("args", {})

                ctx.stage = "tool"
                self.hooks.emit("pre_tool", ctx)
                tool_fn = self.tools[ctx.tool_name]
                ctx.tool_result = tool_fn(**ctx.tool_args)
                self.hooks.emit("post_tool", ctx)

                ctx.final_response = f"工具 {ctx.tool_name} 执行结果：{ctx.tool_result}"
            else:
                ctx.final_response = ctx.parsed["answer"]

            ctx.stage = "response"
            self.hooks.emit("pre_response", ctx)

            if stream:
                self.hooks.emit("on_stream_start", ctx)
                result = ""
                for delta in self.llm.stream(ctx.final_response):
                    ctx.metadata["delta"] = delta
                    self.hooks.emit("on_stream_delta", ctx)
                    result += delta
                ctx.final_response = result
                self.hooks.emit("on_stream_end", ctx)

            self.hooks.emit("post_response", ctx)
            self.hooks.emit("on_finish", ctx)

            return ctx.final_response

        except Exception as e:
            ctx.error = e
            self.hooks.emit("on_error", ctx)
            raise

    def _call_llm_with_retry(self, ctx: Context, max_retries: int = 2) -> str:
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                ctx.metadata["retry_attempt"] = attempt
                self.hooks.emit("pre_retry", ctx)
                result = self.llm.generate(ctx.prompt)
                self.hooks.emit("post_retry", ctx)
                return result
            except Exception as e:
                last_error = e

        raise last_error


# -------------------------
# Hook 实现
# -------------------------

def log_start(ctx: Context):
    print("[on_start] Agent started")


def log_finish(ctx: Context):
    print("[on_finish] Agent finished")


def log_error(ctx: Context):
    print(f"[on_error] stage={ctx.stage}, error={ctx.error}")


def input_guard(ctx: Context):
    if len(ctx.user_input) > 1000:
        raise ValueError("Input too long")


def normalize_log(ctx: Context):
    print(f"[post_input] normalized_input={ctx.normalized_input}")


def rewrite_query(ctx: Context):
    ctx.normalized_input += " LLM Agent Hook Python 示例"


def filter_docs(ctx: Context):
    ctx.docs = [doc for doc in ctx.docs if doc["score"] >= 0.8]
    print(f"[post_retrieval] kept_docs={len(ctx.docs)}")


def limit_docs(ctx: Context):
    ctx.docs = ctx.docs[:3]


def add_prompt_rule(ctx: Context):
    ctx.metadata["prompt_rule"] = "回答必须简洁、结构清晰。"


def inspect_prompt(ctx: Context):
    print("[post_prompt] prompt length:", len(ctx.prompt))


def log_cache(ctx: Context):
    print("[pre_cache] checking cache")


def log_llm_request(ctx: Context):
    ctx.metadata["llm_start"] = time.time()
    print("[pre_llm] calling LLM")


def log_llm_response(ctx: Context):
    elapsed = time.time() - ctx.metadata["llm_start"]
    print(f"[post_llm] output={ctx.llm_output}")
    print(f"[post_llm] elapsed={elapsed:.4f}s")


def validate_json(ctx: Context):
    if not isinstance(ctx.parsed, dict):
        raise ValueError("LLM output must be JSON object")


def tool_permission(ctx: Context):
    print(f"[pre_tool] tool={ctx.tool_name}, args={ctx.tool_args}")
    if ctx.tool_name not in {"calculator", "search"}:
        raise PermissionError(f"Tool not allowed: {ctx.tool_name}")


def tool_audit(ctx: Context):
    print(f"[post_tool] result={ctx.tool_result}")


def format_response(ctx: Context):
    ctx.final_response = f"最终答案：{ctx.final_response}"


def stream_delta_log(ctx: Context):
    print(ctx.metadata["delta"], end="", flush=True)


def retry_log(ctx: Context):
    print(f"[pre_retry] attempt={ctx.metadata['retry_attempt']}")


# -------------------------
# Demo
# -------------------------

if __name__ == "__main__":
    agent = Agent()

    agent.hooks.register("on_start", log_start)
    agent.hooks.register("on_finish", log_finish)
    agent.hooks.register("on_error", log_error)

    agent.hooks.register("pre_input", input_guard)
    agent.hooks.register("post_input", normalize_log)

    agent.hooks.register("pre_retrieval", rewrite_query)
    agent.hooks.register("post_retrieval", filter_docs)

    agent.hooks.register("pre_rerank", limit_docs)

    agent.hooks.register("pre_prompt", add_prompt_rule)
    agent.hooks.register("post_prompt", inspect_prompt)

    agent.hooks.register("pre_cache", log_cache)

    agent.hooks.register("pre_llm", log_llm_request)
    agent.hooks.register("post_llm", log_llm_response)

    agent.hooks.register("pre_parse", lambda ctx: print("[pre_parse] parsing LLM output"))
    agent.hooks.register("post_parse", validate_json)

    agent.hooks.register("pre_tool", tool_permission)
    agent.hooks.register("post_tool", tool_audit)

    agent.hooks.register("pre_response", format_response)

    agent.hooks.register("on_stream_start", lambda ctx: print("[stream_start]"))
    agent.hooks.register("on_stream_delta", stream_delta_log)
    agent.hooks.register("on_stream_end", lambda ctx: print("\n[stream_end]"))

    agent.hooks.register("pre_retry", retry_log)

    print("\n--- 普通问答 ---")
    print(agent.run("什么是 Hook？"))

    print("\n--- 工具调用 ---")
    print(agent.run("请帮我计算 1 + 2 * 3"))

    print("\n--- 流式输出 ---")
    print(agent.run("什么是 Agent Hook？", stream=True))