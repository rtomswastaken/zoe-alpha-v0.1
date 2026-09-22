# Zoe (Z-O-E) — Personal Local AI Computer Assistant for macOS

> **Phase 1: Native Mac Control Foundation (100% Local)**

Zoe is a personal, private, on-device AI voice assistant and computer-use agent for macOS. 

This repository contains **Phase 1: Mac Control**, which provides a deterministic, visible, native macOS control layer using Apple Silicon CoreGraphics / Quartz, AppKit, and Accessibility APIs with zero cloud dependencies and zero telemetry.

---

## 1. Project Structure

```
zoe/
├── config/
│   ├── __init__.py
│   ├── config.yaml          # Speeds, curves, display settings, safety limits
│   └── settings.py          # Strongly-typed configuration loader
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
├── cli.py                   # Comprehensive CLI runner with 21-point acceptance test suite
├── main.py                  # CLI entrypoint
└── requirements.txt         # Project dependencies
```

---

## 2. Dependencies

Zoe Phase 1 strictly avoids cross-platform wrappers like PyAutoGUI and runs directly on native macOS PyObjC frameworks:

- `pyobjc-core`: Objective-C bridge for Python on Apple Silicon (`arm64`).
- `pyobjc-framework-Quartz`: CoreGraphics (`CGEvent`, `CGWindowListCreateImage`, `CGDisplay`).
- `pyobjc-framework-ApplicationServices`: macOS Accessibility API (`AXUIElementCopyAttributeValue`).
- `pyobjc-framework-Cocoa`: AppKit workspace & application management (`NSWorkspace`).
- `pillow`: Image processing utilities.
- `pyyaml`: Configuration file parser.

To install dependencies:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

---

## 3. macOS Permissions Required

Before Zoe can control your Mac and inspect UI elements, two standard macOS permissions must be granted:

1. **Accessibility**:
   *Path:* System Settings > Privacy & Security > Accessibility
   *Required for:* Smooth cursor movement, mouse clicks, keyboard keystrokes, and `AXUIElement` UI tree inspection.
2. **Screen Recording**:
   *Path:* System Settings > Privacy & Security > Screen & System Audio Recording
   *Required for:* Capturing local desktop screenshots and window bounds.

You can verify permission status at any time:
```bash
python -m zoe.main check-permissions
```

---

## 4. Running Zoe Phase 1

### Verify Permissions
```bash
python -m zoe.main check-permissions
```

### Run the 21-Point Acceptance Test Suite
```bash
python -m zoe.main test-all
```

### List Registered Tools
```bash
python -m zoe.main list-tools
```

### Interactive CLI Mode
```bash
python -m zoe.main interactive
```
Available interactive commands:
- `move <x> <y> [duration]` — Smoothly moves the cursor across the screen
- `click [x] [y] [left|right]` — Clicks at coordinates or current position
- `doubleclick [x] [y]` — Double clicks at coordinates
- `drag <x1> <y1> <x2> <y2>` — Visibly drags between coordinates
- `scroll <vert> [horiz]` — Emits native scroll wheel events
- `type <text>` — Types text visibly on keyboard with realistic delays
- `press <key>` — Presses a key (e.g. `return`, `space`, `escape`, `tab`, `f1`)
- `hotkey <key1> <key2> ...` — Executes shortcuts (e.g. `hotkey command space`)
- `app <name>` — Launches or focuses an application (e.g. `app Calculator`)
- `close <name>` — Closes a running application
- `active` — Inspects the frontmost application and PID
- `windows` — Lists active on-screen windows and bounds
- `screenshot [path]` — Captures a local desktop screenshot
- `tree [app]` — Traverses and prints the Accessibility tree hierarchy
- `stop` — Triggers emergency stop
- `reset` — Resets emergency stop
- `test` — Runs full acceptance suite
- `exit` — Quits interactive mode

---

## 5. Emergency Stop Mechanism

Zoe has an immediate fail-safe:
- Pressing physical **`ESC`** (or calling `emergency_controller.trigger()`) immediately halts active cursor trajectories, drag operations, and keystrokes.
- It immediately releases any held mouse buttons.
- Any pending queued actions are rejected.
- You can reset the stop state via `emergency_controller.reset()` or `reset` in the CLI.

---

## 6. Structured Results & LLM Handoff (Phase 2)

Every tool in Zoe returns a structured JSON dictionary:
```json
{
  "success": true,
  "action": "click",
  "coordinates": [842, 611],
  "button": "left",
  "message": "Left click completed at (842.0, 611.0)"
}
```

Errors are also strictly structured:
```json
{
  "success": false,
  "action": "get_accessibility_tree",
  "error": "Accessibility permission not granted in System Settings",
  "error_code": -25211
}
```

### Plugging in the Local LLM in Phase 2

In Phase 2, the local LLM (running via Ollama, llama.cpp, or MLX-LM) interfaces with the system directly through `ToolRegistry`:

1. **Retrieve JSON Schema Definitions:**
   ```python
   from zoe.tools.registry import tool_registry
   llm_tools = tool_registry.get_schema_definitions()
   ```
   This outputs standard OpenAI/Ollama-compatible tool schemas.

2. **Dispatch Tool Calls:**
   When the local LLM generates a function call:
   ```python
   tool_name = llm_response["tool_call"]["name"]
   arguments = llm_response["tool_call"]["arguments"]
   
   result = tool_registry.execute(tool_name, **arguments)
   ```
   The result is fed back into the local LLM context to verify completion.

---

## 7. Known Limitations

- **Accessibility Sandboxing:** Certain proprietary electron or sandboxed apps may not expose their complete internal widget tree via `AXUIElement`. When an element cannot be found in the Accessibility tree, Zoe will fall back to local computer vision in Phase 3.
- **Full-Screen Games / Exclusive Mode:** Apps using exclusive fullscreen or raw HID capture bypass standard Quartz window event queues.
