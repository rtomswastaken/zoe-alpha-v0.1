# Zoe (Z-O-E) — Personal Local AI Computer Assistant for macOS

> **Phase 1: Native Mac Control Foundation (100% Local)**  
> **Phase 2: Local AI Brain (100% On-Device Ollama Inference)**

Zoe is a personal, private, on-device AI voice assistant and computer-use agent for macOS. 

Everything runs **100% locally on your Mac** with zero cloud APIs, zero telemetry, and zero data leaving your device.

---

## 1. Architecture

```
User Command (e.g. "Open Safari and open a new tab")
      ↓
ZoeAgent & State Management
      ↓
LocalModel (Ollama / qwen3:14b default)
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

### Safety & Control Guarantee
- The LLM has **zero direct shell or python access**.
- It interacts with macOS **exclusively** through validated functions registered in `ToolRegistry`.
- An immediate **Emergency Stop (`ESC`)** breaks running cursor/drag loops, releases buttons, and halts planning.

---

## 2. Project Structure

```
zoe/
├── config/
│   ├── __init__.py
│   ├── config.yaml          # Speeds, curves, display settings, model config
│   └── settings.py          # Strongly-typed configuration loader
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
├── macos/
│   ├── __init__.py
│   ├── permissions.py       # Accessibility & Screen Recording permission checker
│   ├── display.py           # Multi-monitor enumeration, Retina scaling & coordinate math
│   ├── emergency.py         # Global emergency stop controller (ESC) & action cancel token
│   ├── logger.py            # Local privacy-respecting action logger
│   ├── cursor.py            # Visible, smooth Bezier cursor trajectory & positioning
│   ├── mouse.py             # Native CGEvent clicks, double clicks, right clicks, drags, scrolls
│   ├── keyboard.py          # Native CGEvent key presses, hotkeys, unicode text typing
│   ├── apps.py              # NSWorkspace app lifecycle (launch, activate, quit, list, window bounds)
│   ├── accessibility.py     # Native AXUIElement hierarchy traversal & UI inspection
│   └── screenshots.py       # High-speed local Quartz screen capture (memory/local disk only)
├── tools/
│   ├── __init__.py
│   ├── base.py              # Base tool contract & structured result serialization
│   ├── registry.py          # Central tool registry with JSON-schema export for Phase 2 LLM
│   ├── computer.py          # Mouse, cursor, keyboard, display, screenshot tool definitions
│   └── applications.py      # App lifecycle & accessibility tree tool definitions
├── cli.py                   # Comprehensive CLI runner with 21-point acceptance suite & Chat REPL
├── main.py                  # CLI entrypoint
└── requirements.txt         # Project dependencies
```

---

## 3. Configuration (`config/config.yaml`)

```yaml
model:
  provider: "ollama"
  name: "qwen3:14b"           # default model; qwen3-coder:30b is also supported
  endpoint: "http://127.0.0.1:11434"
  temperature: 0.1
  max_tokens: 2048
  timeout: 60.0

agent:
  max_tool_calls: 30
  timeout_seconds: 300.0
```

---

## 4. Commands

### Check Local AI Model Status
```bash
.venv/bin/python -m zoe.main model-status
```
Output:
```
ZOE LOCAL AI
────────────────────────────────
Provider:    Ollama
Model:       qwen3:14b
Endpoint:    http://127.0.0.1:11434
Status:      AVAILABLE
Inference:   LOCAL
Network AI:  DISABLED
────────────────────────────────
✓ Local model is online and ready for private inference.
```

### Start Natural-Language Chat REPL
```bash
.venv/bin/python -m zoe.main chat
```
Example interaction:
```
Zoe> Open Calculator and then close it.

[Zoe Thinking...]
[Actions Executed (2) in 2.15s]
  ✓ open_app({'app_name': 'Calculator'})
  ✓ close_app({'app_name': 'Calculator'})

Zoe: I have opened Calculator and then closed it for you.
```

### Check Permissions & Run Acceptance Suite
```bash
.venv/bin/python -m zoe.main check-permissions
.venv/bin/python -m zoe.main test-all
```

### Run All Unit & Integration Tests
```bash
.venv/bin/pytest tests/ -v
```
Currently 42/42 tests pass.

---

## 5. Privacy & Emergency Stop

- **100% Offline Capable:** Runs disconnected from the internet. All inference goes through `http://127.0.0.1:11434`.
- **Sensitive Text Masking:** Passwords and sensitive text are masked in `logs/zoe.log`.
- **Global Fail-Safe (ESC):** Physical `ESC` halts all cursor trajectories, drag operations, releases mouse buttons, and terminates the agent loop immediately.
