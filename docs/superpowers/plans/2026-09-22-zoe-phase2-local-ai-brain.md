# Zoe Phase 2: Local AI Brain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate a 100% local, native LLM reasoning engine (Ollama with `qwen3:14b` default, `qwen3-coder:30b` configurable) on top of the Phase 1 computer control foundation, executing multi-step natural language instructions with observable visible actions, emergency stop cancellation, and zero cloud dependencies.

**Architecture:** Abstract `LocalModel` layer with native `urllib.request` `OllamaModel`, decoupled `AgentState`, dedicated `SystemPrompt`, and an observe-think-act `AgentLoop` that translates natural language commands into Phase 1 `ToolRegistry` calls.

**Tech Stack:** Python 3.14, built-in `urllib.request` (zero new pip packages), Ollama REST API (`/api/chat`, `/api/tags`), existing Phase 1 tools (`Quartz`, `ApplicationServices`, `AppKit`).

**Spec:** [docs/superpowers/specs/2026-09-22-zoe-phase2-local-ai-brain-design.md](../specs/2026-09-22-zoe-phase2-local-ai-brain-design.md)

## Global Constraints

- **Platform:** macOS Apple Silicon (`arm64`), Python 3.14 `.venv`.
- **Default Provider & Model:** `ollama`, `qwen3:14b` (configurable to `qwen3-coder:30b` or others).
- **100% Local Only:** Ollama endpoint strictly bound to `http://127.0.0.1:11434`. Zero cloud APIs, zero telemetry.
- **Safety:** No arbitrary shell or python execution. The LLM only calls tools registered in Phase 1's `ToolRegistry`.
- **Emergency Stop:** Immediate abort on `ESC` cancels running tools and terminates the LLM planning loop.
- **Preservation:** Phase 1 tools remain unchanged.

---

## Tasks

### Task 1: Verify Pre-Flight Ollama Tool Calling Capability
- Run live probe against local Ollama (`http://127.0.0.1:11434`) confirming `qwen3:14b` presence, basic chat, and tool call parsing on Phase 1 tool schemas.

### Task 2: Config and Settings Update
- Update `zoe/config/config.yaml` to include `model` and `agent` sections.
- Update `zoe/config/settings.py` to add typed `ModelConfig` and `AgentConfig`.
- Test: `tests/test_config_phase2.py`.

### Task 3: Local Model Abstraction Layer
- Create `zoe/models/__init__.py`.
- Create `zoe/models/base.py`: `ToolCall`, `ModelResponse`, `LocalModel`.
- Test: `tests/test_models_base.py`.

### Task 4: Native Ollama Client via `urllib.request`
- Create `zoe/models/ollama.py`: `OllamaModel` implementing `/api/chat` with tool schemas and `/api/tags`.
- Create `zoe/models/factory.py`: `get_model(config)` factory.
- Test: `tests/test_ollama_model.py` (with mocked HTTP and live integration tests).

### Task 5: System Prompt and Agent State
- Create `zoe/agent/__init__.py`.
- Create `zoe/agent/prompts.py`: Zoe system prompt.
- Create `zoe/agent/state.py`: `AgentState`.
- Test: `tests/test_agent_state.py`.

### Task 6: Planner & Observe-Think-Act Loop
- Create `zoe/agent/planner.py`: Message preparation and tool result formatting.
- Create `zoe/agent/loop.py`: `AgentLoop` with timeout, max iteration cap, invalid tool recovery, and ESC emergency stop check.
- Create `zoe/agent/agent.py`: `ZoeAgent` top-level interface (`run_task(task_description)`).
- Test: `tests/test_agent_loop.py`.

### Task 7: CLI Extensions (Model Status & Chat REPL)
- Update `zoe/cli.py` to add `cmd_model_status()` and `cmd_chat()`.
- Update `zoe/main.py` with subcommands `model-status` and `chat`.
- Test: `tests/test_cli_phase2.py`.

### Task 8: End-to-End Multi-Step Verification & Phase 1 Regression
- Run complete test suite (Phase 1 + Phase 2).
- Execute basic tests and multi-step tasks (e.g. open app, focus, close, move cursor, type text).

---

## Verification Plan

### Automated Unit Tests
```bash
.venv/bin/pytest tests/ -v
```

### Model Health Verification
```bash
.venv/bin/python -m zoe.main model-status
```

### Live Multi-Step Command Execution
```bash
.venv/bin/python -c "from zoe.agent.agent import ZoeAgent; agent = ZoeAgent(); print(agent.run_task('Open Calculator and close it.'))"
```
