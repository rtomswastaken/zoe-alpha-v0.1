# Zoe Phase 2: Local AI Brain Design Specification

**Status:** Approved  
**Platform:** macOS Apple Silicon (arm64)  
**Date:** 2026-09-22  
**Target:** 100% Local Inference, Ollama (`qwen3:14b`), native Python `urllib.request`, zero cloud, zero telemetry.

---

## 1. Overview & Architecture

Phase 2 builds the cognitive planning and execution layer directly on top of Phase 1's computer-control foundation.

```
User Command (e.g. "Open Safari and open a new tab")
      ↓
ZoeAgent & State Management
      ↓
LocalModel (Ollama / qwen3:14b) via /api/chat
      ↓
Tool Selection (e.g. open_app("Safari"))
      ↓
ToolRegistry (Phase 1)
      ↓
macOS Action (Visible cursor / window activation)
      ↓
Structured Tool Result ({"success": true, ...})
      ↓
LocalModel (Observe state & plan next step)
      ↓
Tool Selection (e.g. hotkey(["command", "t"]))
      ↓
ToolRegistry (Phase 1)
      ↓
Structured Tool Result
      ↓
LocalModel
      ↓
Final Response ("Opened Safari and opened a new tab.")
```

---

## 2. Directory Structure

```
zoe/
├── config/
│   ├── config.yaml          # Added: model provider, name (default: qwen3:14b), temperature, max_tool_calls
│   └── settings.py          # Strongly-typed ModelConfig and AgentConfig
├── models/
│   ├── __init__.py
│   ├── base.py              # Abstract LocalModel, ModelResponse, ToolCall
│   ├── ollama.py            # Native OllamaModel implementing /api/chat with tools via urllib.request
│   └── factory.py           # get_model(config) factory
├── agent/
│   ├── __init__.py
│   ├── state.py             # AgentState (task, active_app, recent_actions, tool_results, iteration_count, cancelled)
│   ├── prompts.py           # Dedicated Zoe system prompt
│   ├── loop.py              # Observe-think-act agent loop with timeout, tool execution, iteration cap & ESC abort
│   └── agent.py             # ZoeAgent coordinator
├── tools/
│   └── (Existing Phase 1 tools unchanged)
├── cli.py                   # Extended with `model-status` and interactive `chat` (Zoe> ...)
└── main.py                  # CLI entrypoint routing
```

---

## 3. Subsystem Specifications

### 3.1 Model Abstraction (`zoe/models/base.py`)
- `ToolCall`: Dataclass containing `id: str`, `name: str`, `arguments: Dict[str, Any]`.
- `ModelResponse`: Dataclass containing `text: Optional[str]`, `tool_calls: List[ToolCall]`, `raw: Dict[str, Any]`.
  - Helper methods: `has_tool_calls() -> bool`.
- `LocalModel` (Abstract Base Class):
  - `chat(messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None, temperature: Optional[float] = None) -> ModelResponse`
  - `is_available() -> bool`
  - `model_info() -> Dict[str, Any]`

### 3.2 Ollama REST Model (`zoe/models/ollama.py`)
- Uses Python `urllib.request` against `http://127.0.0.1:11434`.
- Availability: checks `GET /api/tags` and verifies whether the configured model (e.g. `qwen3:14b`) is present in the models list.
- Chat: `POST /api/chat` with JSON body:
  ```json
  {
    "model": "qwen3:14b",
    "messages": [...],
    "tools": [...],
    "stream": false,
    "options": {
      "temperature": 0.1,
      "num_predict": 2048
    }
  }
  ```
- Normalizes response into `ModelResponse` and parses any `tool_calls`. Handles JSON argument parsing safely with fallback recovery if model outputs stringified JSON or markdown codeblocks.

### 3.3 System Prompt (`zoe/agent/prompts.py`)
- Emphasizes:
  - Role: Zoe, a personal computer-use assistant running 100% locally on macOS.
  - Authority: Controls Mac strictly through provided tools.
  - Observation: Observe current state before acting when necessary.
  - Native Priority: Prefer macOS Accessibility information when available.
  - Accuracy: Never invent coordinates; never hallucinate tool outcomes.
  - Safety: Destructive operations require user confirmation.
  - Brevity: Keep responses concise and natural.

### 3.4 State Tracking (`zoe/agent/state.py`)
- `AgentState`:
  - `task: str`
  - `active_app: str`
  - `recent_actions: List[Dict[str, Any]]`
  - `tool_results: List[Dict[str, Any]]`
  - `iteration_count: int`
  - `cancelled: bool`
  - `is_complete: bool`
  - `final_response: Optional[str]`

### 3.5 Agent Loop (`zoe/agent/loop.py` & `zoe/agent/agent.py`)
- Iterative loop with:
  - Max tool calls per task cap (`max_tool_calls`, default 30).
  - Timeout check per iteration.
  - Integration with Phase 1 `emergency_controller`:
    - Checks `emergency_controller.is_stopped()` before each tool call and LLM call.
    - If ESC is pressed, immediately cancels the task and returns control to the user.
  - Validates tool names against `tool_registry`. Unknown tools return structured error directly into conversation context without crashing.
  - Structured results from tools are converted to standard `role: "tool"` or `role: "user"` message entries for the LLM to observe.

### 3.6 CLI Commands
- `zoe model-status`: Displays formatted local model health, provider, model name, inference locality, and network isolation status.
- `zoe chat`: Starts an interactive `Zoe> ` REPL where user speaks/types instructions, watching actions execute live on the Mac.
