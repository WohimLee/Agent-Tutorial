# client_ws.py
import os
import json
import asyncio
from typing import Dict, Any, List

from openai import OpenAI

import mcp
from mcp.client.websocket import websocket_client

from dotenv import load_dotenv
load_dotenv("/Users/azen/Desktop/llm/.env")

############################################
# 1. 初始化 LLM 客户端（Qwen）
############################################

llm_client = OpenAI(
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url=os.getenv("DASHSCOPE_API_URL"),
)

MODEL_NAME = "qwen3-max"

############################################
# 2. System 提示词
############################################

SYSTEM_MESSAGE = {
    "role": "system",
    "content": (
        "你是一个会主动使用工具的智能助手。"
        "当你需要查询实时信息、天气等时，请优先调用提供的工具。"
        "你可以多次调用工具，直到拿到足够信息后，再给出中文回答。"
    ),
}

############################################
# 3. 从 MCP 读取工具列表，转换为 OpenAI tools schema
############################################


async def get_oai_tools_from_mcp(session: mcp.ClientSession) -> List[Dict[str, Any]]:
    """
    从 MCP server 获取工具列表，并转换成 OpenAI Chat Completions 用的 tools schema。
    """
    tools_result = await session.list_tools()
    mcp_tools = [tool.model_dump() for tool in tools_result.tools]

    oai_tools: List[Dict[str, Any]] = []
    for t in mcp_tools:
        input_schema = t.get("inputSchema") or {}

        oai_tools.append(
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": input_schema,
                },
            }
        )

    return oai_tools


async def call_mcp_tool(
    session: mcp.ClientSession, tool_name: str, tool_args: Dict[str, Any]
) -> str:
    """
    调用 MCP tool，把返回的内容（TextContent 等）拼成一个字符串给 LLM。
    """
    result = await session.call_tool(name=tool_name, arguments=tool_args)

    parts: List[str] = []
    for item in result.content:
        # 只取文本内容，其他类型（图片、资源）简单 str() 一下
        text = getattr(item, "text", None)
        if text is not None:
            parts.append(text)
        else:
            parts.append(str(item))

    return "\n".join(parts)


############################################
# 4. LLM 调用封装（带 tools）
############################################


def call_llm_with_tools(
    history: List[Dict[str, Any]], tools: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    调一次 LLM，让它决定是否调用工具（tool_choice='auto'）。
    返回 ChatCompletionMessage（dict）。
    """
    response = llm_client.chat.completions.create(
        model=MODEL_NAME,
        messages=history,
        tools=tools,
        tool_choice="auto",
        stream=False,
    )
    return response.choices[0].message


def final_summarize(history: List[Dict[str, Any]]) -> str:
    """
    最终总结阶段：禁止继续调工具，用流式输出打印最终回答。
    """
    print("助手：", end="", flush=True)

    stream = llm_client.chat.completions.create(
        model=MODEL_NAME,
        messages=history,
        stream=True,
        tool_choice="none",  # 最终阶段禁止工具调用
    )

    full_content = ""
    for chunk in stream:
        delta = chunk.choices[0].delta
        content = getattr(delta, "content", None) or ""
        if content:
            print(content, end="", flush=True)
            full_content += content
    print()
    return full_content


async def run_agent_once(
    user_input: str,
    history: List[Dict[str, Any]],
    mcp_session: mcp.ClientSession,
    oai_tools: List[Dict[str, Any]],
    max_tool_rounds: int = 5,
) -> str:
    """
    针对一次用户输入，执行一个完整的 agent 流程（基于 MCP 工具）：
    - 多轮工具调用（最多 max_tool_rounds 轮）
    - 最后使用 stream=True 做自然语言总结
    返回最终完整回复字符串。
    """
    # 先把用户输入 push 到 history
    history.append({"role": "user", "content": user_input})

    # 工具调用循环
    for _ in range(max_tool_rounds):
        msg = call_llm_with_tools(history, tools=oai_tools)

        assistant_msg: Dict[str, Any] = {
            "role": "assistant",
            "content": msg.content,
        }
        if msg.tool_calls:
            assistant_msg["tool_calls"] = msg.tool_calls
        history.append(assistant_msg)

        # 没有 tool_calls，说明模型认为已经可以直接回答
        if not msg.tool_calls:
            break

        # 有 tool_calls -> 通过 MCP 调用真实工具
        for tool_call in msg.tool_calls:
            tool_name = tool_call.function.name
            raw_args = tool_call.function.arguments or "{}"

            try:
                if isinstance(raw_args, str):
                    tool_args = json.loads(raw_args)
                else:
                    tool_args = raw_args
            except json.JSONDecodeError:
                tool_args = {}

            print("模型要求调用函数：", tool_name, "参数：", tool_args)

            try:
                tool_result = await call_mcp_tool(
                    session=mcp_session, tool_name=tool_name, tool_args=tool_args
                )
            except Exception as e:
                tool_result = f"[调用 MCP 工具 {tool_name} 出错: {e!r}]"

            # 把工具结果塞回 messages
            history.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_name,
                    "content": str(tool_result),
                }
            )

    # 工具阶段结束 -> 做最终自然语言回答
    final_answer = final_summarize(history)
    history.append({"role": "assistant", "content": final_answer})
    return final_answer


############################################
# 5. 历史裁剪 + 主循环
############################################


def truncate_history(
    history: List[Dict[str, Any]], max_messages: int = 30
) -> List[Dict[str, Any]]:
    """
    简单的历史裁剪：只保留最近 max_messages 条消息（加上 system）。
    """
    msgs = [m for m in history if m["role"] != "system"]
    if len(msgs) <= max_messages:
        return history

    new_history = [SYSTEM_MESSAGE] + msgs[-max_messages:]
    return new_history


async def chat_loop():
    """
    通过 WebSocket 连接本地 MCP server（server_ws.py），并进入多轮对话。
    """
    ws_url = "ws://127.0.0.1:8000/mcp/"

    print(f"准备通过 WebSocket 连接 MCP 服务：{ws_url}")

    # 建立 WebSocket 连接，拿到 read / write 流
    async with websocket_client(ws_url) as (read_stream, write_stream):
        # 创建 MCP ClientSession
        async with mcp.ClientSession(read_stream, write_stream) as mcp_session:
            # 初始化 MCP 会话（协商版本/能力）
            await mcp_session.initialize()

            # 从 MCP server 获取工具列表，并转换成 OpenAI tools schema
            oai_tools = await get_oai_tools_from_mcp(mcp_session)

            history: List[Dict[str, Any]] = [SYSTEM_MESSAGE]

            print("已启动 MCP WebSocket 工具增强 Agent，对话中输入 exit / 退出 即可结束。")

            while True:
                user_input = input("用户：").strip()
                if user_input.lower() in {"exit", "quit", "q", "退出"}:
                    print("再见 👋")
                    break

                history = truncate_history(history)

                try:
                    await run_agent_once(
                        user_input,
                        history,
                        mcp_session=mcp_session,
                        oai_tools=oai_tools,
                    )
                except Exception as e:
                    print(f"\n[调用出错]: {e!r}\n")


def main():
    asyncio.run(chat_loop())


if __name__ == "__main__":
    main()
