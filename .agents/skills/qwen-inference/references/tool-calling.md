# Tool calling

Qwen3.5 is strong at tool calling / function calling. The official docs reference **Qwen-Agent** and **Qwen Code** as the ecosystem agentic frameworks. But tool calling only works if the backend, parser, and client layer are all correctly aligned.

## The three-layer requirement

Tool calling is **not** a prompt property. Getting it to work requires:

1. **Backend launched with the correct parser.** On vLLM: `--tool-call-parser qwen3_coder` + `--enable-auto-tool-choice`. On SGLang: `--tool-call-parser qwen3_coder`. Without this, tool outputs are emitted as raw text, not parsed into structured events.
2. **Chat template that includes the tool-use schema.** The shipped Qwen3.5 chat template already supports this; do not override it unless you know why.
3. **Client code that sends tools in OpenAI tool-calling format and handles the structured response.**

Skipping any of these three gets you "prompt-engineered tool calling" — fragile, unreliable, and not what the model was trained for.

## Client-side tool declaration

Declare tools as strict JSON schemas. Vague or under-specified schemas hurt call quality:

```python
tools = [
    {
        "type": "function",
        "function": {
            "name": "buscar_documento",
            "description": "Busca un documento interno por ID o título. Retorna el texto del documento encontrado o null si no existe.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Título parcial o ID exacto del documento.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Número máximo de documentos a retornar. Por defecto 5.",
                        "minimum": 1,
                        "maximum": 20,
                    },
                },
                "required": ["query"],
            },
        },
    },
]
```

Good schema hygiene:

- Every parameter has a description, not just a name.
- Types are specific (`integer`, not `number`, when integers are required).
- `required` is explicit.
- `minimum`/`maximum`/`enum` are used where they constrain real inputs.
- The function description states what the tool returns, not just what it does.

## Invocation

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="EMPTY")

response = client.chat.completions.create(
    model="Qwen/Qwen3.5-9B",
    messages=[
        {"role": "user", "content": "Busca el documento con título 'protocolo clínico 2024'"},
    ],
    tools=tools,
    tool_choice="auto",
    temperature=0.6,
    extra_body={"top_k": 20},
)

msg = response.choices[0].message

if msg.tool_calls:
    for tool_call in msg.tool_calls:
        name = tool_call.function.name
        args = json.loads(tool_call.function.arguments)
        # execute the tool
        result = dispatch_tool(name, args)
        # feed result back
        messages.append(msg)  # the assistant's tool call
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": json.dumps(result),
        })
    # re-invoke to get final answer
    followup = client.chat.completions.create(
        model="Qwen/Qwen3.5-9B",
        messages=messages,
        tools=tools,
    )
```

## Validation layer

Never blindly execute what the model emits. Validate args against the schema, enforce limits, and run execution in an isolated context:

```python
from jsonschema import validate, ValidationError

def dispatch_tool(name: str, args: dict) -> dict:
    if name not in TOOL_REGISTRY:
        raise ValueError(f"Unknown tool: {name}")

    tool = TOOL_REGISTRY[name]
    try:
        validate(instance=args, schema=tool.schema)
    except ValidationError as e:
        return {"error": f"Invalid arguments: {e.message}"}

    try:
        return tool.execute(args)
    except Exception as e:
        # Return error to model, don't leak stack trace
        return {"error": f"Tool execution failed: {type(e).__name__}"}
```

## History with tool calls

Tool calls complicate history sanitization. The assistant message containing the tool call **and** the corresponding tool response must both be retained for the model to understand what it did — but reasoning around tool calls still should not persist across turns.

Pattern:

```python
# Keep in history:
# - user messages
# - assistant messages with tool_calls (but not the reasoning that led to them)
# - tool responses

# Drop from history:
# - reasoning tokens on any assistant message
# - internal "scratchpad" content
```

## Agent loop shape

A minimal correct agent loop:

```python
MAX_STEPS = 10

def agent_loop(user_input: str, messages: list, tools: list) -> str:
    messages.append({"role": "user", "content": user_input})

    for step in range(MAX_STEPS):
        response = client.chat.completions.create(
            model="Qwen/Qwen3.5-9B",
            messages=messages,
            tools=tools,
            tool_choice="auto",
            max_tokens=4096,   # per-step budget, not total
        )
        msg = response.choices[0].message

        if not msg.tool_calls:
            # Final answer
            messages.append(sanitize_assistant_message(msg))
            return msg.content

        # Execute all tool calls in this step
        messages.append(msg)  # retain the tool_calls message
        for tc in msg.tool_calls:
            result = dispatch_tool(tc.function.name, json.loads(tc.function.arguments))
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result),
            })

    raise RuntimeError(f"Agent exceeded {MAX_STEPS} steps without producing final answer")
```

Key decisions in the loop:

- **`MAX_STEPS` cap.** Prevents infinite tool-calling loops.
- **Per-step `max_tokens`**, not global. Each step should be bounded; total across loop is the sum.
- **`tool_choice="auto"`**. `"required"` forces a tool call even when the model shouldn't use one. `"none"` disables tools entirely.
- **Parallel tool calls** are possible — the model may emit multiple `tool_calls` in one response. Execute them and return results in the same tool-response batch.

## Ollama and tool calling

Ollama supports tool calling via the `tools` field in the chat API, but the parser quality depends on the shipped template for `qwen3.5:9b`. Smoke-test before committing to this path in production — if you see tool calls emitted as raw JSON in text content instead of structured `tool_calls`, the template is not parsing correctly and you need to either override the Modelfile or switch to vLLM/SGLang.

## Common failures

- **Tool call never fires.** Usually a schema issue: description too vague, or required parameters that don't match user intent. Improve schema first.
- **Tool call fires but arguments are malformed JSON.** Usually insufficient `max_tokens` truncating the argument block mid-emission, OR thinking mode enabled with insufficient budget. Increase `max_tokens` and/or disable thinking for agent steps.
- **Tool call fires for unnecessary cases.** Add "only use this tool when..." clauses in the function description, and validate at dispatch.
- **Tool result triggers another tool call unnecessarily.** Cap `MAX_STEPS` and log the loop to diagnose; usually a prompt engineering fix (clearer completion signal).
