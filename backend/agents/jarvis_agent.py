import json
import groq
from google import genai
from google.genai import types
from config import (
    GEMINI_API_KEY, GROQ_API_KEY,
    FAST_MODEL, SMART_MODEL,
    FAST_MODEL_WORD_THRESHOLD, USER_ID
)
from tools.search import web_search
from tools.weather import get_weather
from tools.memory import recall_memory, list_memories
from memory.mem0_client import search_memory, store_memory

# Initialize clients
groq_client = groq.Groq(api_key=GROQ_API_KEY)
gemini_client = genai.Client(api_key=GEMINI_API_KEY)

SYSTEM_PROMPT = """You are Jarvis, a highly intelligent, witty, and capable personal AI assistant.
You speak concisely and naturally — like a brilliant assistant, not a search engine.
You have memory of past conversations and can use tools to access real-time information.
Keep responses conversational and brief unless detail is specifically requested.
Your personality: confident, helpful, occasionally dry humor, always efficient."""

# Tool definitions for Gemini (uses different format)
GEMINI_TOOLS = [
    types.Tool(function_declarations=[
        types.FunctionDeclaration(
            name="web_search",
            description="Search the web for current information, news, or facts.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "query": types.Schema(type=types.Type.STRING, description="The search query")
                },
                required=["query"]
            )
        ),
        types.FunctionDeclaration(
            name="get_weather",
            description="Get current weather for a city.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "city": types.Schema(type=types.Type.STRING, description="City name")
                },
                required=["city"]
            )
        ),
        types.FunctionDeclaration(
            name="recall_memory",
            description="Search memory for things the user has told you before.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "query": types.Schema(type=types.Type.STRING, description="What to look for in memory")
                },
                required=["query"]
            )
        ),
        types.FunctionDeclaration(
            name="list_memories",
            description="List all stored memories about the user.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={}
            )
        )
    ])
]

# Tool definitions for Groq (OpenAI format)
GROQ_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for current information, news, or facts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather for a city.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City name"}
                },
                "required": ["city"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "recall_memory",
            "description": "Search memory for things the user has told you before.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "What to look for in memory"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_memories",
            "description": "List all stored memories about the user.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    }
]

def execute_tool(tool_name: str, tool_input: dict) -> str:
    if tool_name == "web_search":
        return web_search(tool_input["query"])
    elif tool_name == "get_weather":
        return get_weather(tool_input["city"])
    elif tool_name == "recall_memory":
        return recall_memory(tool_input["query"])
    elif tool_name == "list_memories":
        return list_memories()
    return "Tool not found."

def select_model(user_message: str) -> str:
    word_count = len(user_message.split())
    simple_triggers = ["what time", "weather", "hello", "hi", "thanks", "ok", "sure", "yes", "no"]
    is_simple = (
        word_count <= FAST_MODEL_WORD_THRESHOLD or
        any(trigger in user_message.lower() for trigger in simple_triggers)
    )
    return FAST_MODEL if is_simple else SMART_MODEL

# ─── GROQ HANDLER ────────────────────────────────────────────────────────────

async def get_groq_response(user_message: str, conversation_history: list, stream_callback=None) -> str:
    memories = search_memory(user_message)
    system = SYSTEM_PROMPT
    if memories:
        system += f"\n\n{memories}"

    messages = [{"role": "system", "content": system}]
    for msg in conversation_history:
        messages.append(msg)
    messages.append({"role": "user", "content": user_message})

    full_response = ""

    while True:
        if stream_callback:
            stream = groq_client.chat.completions.create(
                model=FAST_MODEL,
                messages=messages,
                tools=GROQ_TOOLS,
                tool_choice="auto",
                stream=True,
                max_tokens=1024
            )

            tool_calls_map = {}
            text_chunks = []
            finish_reason = None

            for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if not delta:
                    continue

                finish_reason = chunk.choices[0].finish_reason

                if delta.content:
                    text_chunks.append(delta.content)
                    full_response += delta.content
                    await stream_callback(delta.content)

                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in tool_calls_map:
                            tool_calls_map[idx] = {
                                "id": tc.id or "",
                                "name": tc.function.name or "",
                                "arguments": ""
                            }
                        if tc.id:
                            tool_calls_map[idx]["id"] = tc.id
                        if tc.function.name:
                            tool_calls_map[idx]["name"] = tc.function.name
                        if tc.function.arguments:
                            tool_calls_map[idx]["arguments"] += tc.function.arguments

            tool_calls = list(tool_calls_map.values())

        else:
            response = groq_client.chat.completions.create(
                model=FAST_MODEL,
                messages=messages,
                tools=GROQ_TOOLS,
                tool_choice="auto",
                max_tokens=1024
            )
            choice = response.choices[0]
            finish_reason = choice.finish_reason
            text_chunks = [choice.message.content or ""]
            full_response = choice.message.content or ""
            tool_calls = []
            if choice.message.tool_calls:
                for tc in choice.message.tool_calls:
                    tool_calls.append({
                        "id": tc.id,
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    })

        if finish_reason != "tool_calls" or not tool_calls:
            break

        # Execute tools
        messages.append({
            "role": "assistant",
            "content": "".join(text_chunks),
            "tool_calls": [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {"name": tc["name"], "arguments": tc["arguments"]}
                }
                for tc in tool_calls
            ]
        })

        for tc in tool_calls:
            args = json.loads(tc["arguments"]) if tc["arguments"] else {}
            result = execute_tool(tc["name"], args)
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": result
            })

        full_response = ""

    return full_response

# ─── GEMINI HANDLER ──────────────────────────────────────────────────────────

async def get_gemini_response(user_message: str, conversation_history: list, stream_callback=None) -> str:
    memories = search_memory(user_message)
    system = SYSTEM_PROMPT
    if memories:
        system += f"\n\n{memories}"

    # Build Gemini contents from history
    contents = []
    for msg in conversation_history:
        role = "user" if msg["role"] == "user" else "model"
        contents.append(types.Content(role=role, parts=[types.Part(text=msg["content"])]))
    contents.append(types.Content(role="user", parts=[types.Part(text=user_message)]))

    full_response = ""

    while True:
        if stream_callback:
            stream = gemini_client.models.generate_content_stream(
                model=SMART_MODEL,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    tools=GEMINI_TOOLS,
                    max_output_tokens=1024
                )
            )

            text_chunks = []
            tool_calls = []

            for chunk in stream:
                if not chunk.candidates:
                    continue
                for part in chunk.candidates[0].content.parts:
                    if hasattr(part, "text") and part.text:
                        text_chunks.append(part.text)
                        full_response += part.text
                        await stream_callback(part.text)
                    elif hasattr(part, "function_call") and part.function_call:
                        tool_calls.append({
                            "name": part.function_call.name,
                            "args": dict(part.function_call.args)
                        })

            finish_reason = chunk.candidates[0].finish_reason if chunk.candidates else "STOP"

        else:
            response = gemini_client.models.generate_content(
                model=SMART_MODEL,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    tools=GEMINI_TOOLS,
                    max_output_tokens=1024
                )
            )
            text_chunks = []
            tool_calls = []
            for part in response.candidates[0].content.parts:
                if hasattr(part, "text") and part.text:
                    text_chunks.append(part.text)
                    full_response = "".join(text_chunks)
                elif hasattr(part, "function_call") and part.function_call:
                    tool_calls.append({
                        "name": part.function_call.name,
                        "args": dict(part.function_call.args)
                    })
            finish_reason = response.candidates[0].finish_reason

        if not tool_calls or str(finish_reason) == "STOP":
            break

        # Append model response with tool calls
        model_parts = [types.Part(text=t) for t in text_chunks]
        for tc in tool_calls:
            model_parts.append(types.Part(function_call=types.FunctionCall(
                name=tc["name"], args=tc["args"]
            )))
        contents.append(types.Content(role="model", parts=model_parts))

        # Execute tools and append results
        tool_response_parts = []
        for tc in tool_calls:
            result = execute_tool(tc["name"], tc["args"])
            tool_response_parts.append(types.Part(function_response=types.FunctionResponse(
                name=tc["name"],
                response={"result": result}
            )))
        contents.append(types.Content(role="user", parts=tool_response_parts))

        full_response = ""

    return full_response

# ─── MAIN ENTRY POINT ────────────────────────────────────────────────────────

async def get_jarvis_response(
    user_message: str,
    conversation_history: list,
    stream_callback=None
) -> str:
    model = select_model(user_message)

    if model == FAST_MODEL:
        response = await get_groq_response(user_message, conversation_history, stream_callback)
    else:
        response = await get_gemini_response(user_message, conversation_history, stream_callback)

    # Store memory
    store_memory([
        {"role": "user", "content": user_message},
        {"role": "assistant", "content": response}
    ])

    return response