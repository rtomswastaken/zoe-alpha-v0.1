# Zoe Phase 1: Mac Control Foundation Design Specification

**Status:** Approved  
**Platform:** macOS Apple Silicon (arm64)  
**Date:** 2026-09-22  
**Target:** 100% Local, zero cloud, native Mac automation foundation (No AI/LLM in Phase 1)

---

## 1. Overview & Core Philosophy

Zoe is a personal local AI computer assistant for macOS. Phase 1 establishes a rock-solid, deterministic, observable, and strictly local macOS control foundation without any AI or cloud dependencies.

Key principles:
1. **100% Local & Privacy-First:** No network requests, no telemetry, no cloud APIs. Audio, screen data, logs, and inputs never leave the device.
2. **Visible Action:** No hidden or simulated bypass APIs. Cursors move visibly across the desktop along smooth, human-like Bezier curves. Clicks, drags, and keystrokes occur directly on the macOS desktop.
3. **Emergency Stop (Fail-Safe):** Immediate halt mechanism (e.g. global ESC hotkey / abort flag) that immediately terminates running mouse/keyboard movements and cancels any pending queued actions.
4. **Structured Results:** Every tool returns a structured dictionary (`{"success": bool, "action": str, ...}`) designed for clean, direct consumption by the Phase 2 local LLM planner.
5. **Robust Display & Retina Awareness:** Native coordinate translation accounting for Retina pixel densities, multi-display topologies, and menu bar offsets.
6. **Zero PyAutoGUI:** Built exclusively on native macOS frameworks via PyObjC (`Quartz/CoreGraphics`, `ApplicationServices/HIServices`, `AppKit/Cocoa`).

---

## 2. Directory & Module Architecture

```
zoe/
├── __init__.py
├── config/
│   ├── __init__.py
│   ├── config.yaml          # Speeds, curves, display settings, safety limits
│   └── settings.py          # Strongly-typed configuration loader
├── macos/
│   ├── __init__.py
│   ├── permissions.py       # Accessibility & Screen Recording permission verifier
│   ├── display.py           # Multi-monitor enumeration, Retina scaling & coordinate math
│   ├── emergency.py         # Global emergency-stop monitor (ESC) & task cancellation token
│   ├── logger.py            # Local privacy-respecting event logger
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
└── main.py                  # CLI entrypoint
```

---

## 3. Subsystem Specifications

### 3.1 Display & Coordinate Translation (`macos/display.py`)
- Uses `CGGetActiveDisplayList`, `CGDisplayBounds`, `CGMainDisplayID()`.
- Calculates display scale factors (`NSScreen.backingScaleFactor` or display mode pixel-width vs point-width).
- Provides conversion between Point Coordinates (Cocoa / CGEvent virtual space) and Physical Pixel Coordinates (for screenshots and vision).
- Handles multi-monitor setups: bounds checking, identifying which monitor contains a given `(x, y)` coordinate.

### 3.2 Emergency Stop (`macos/emergency.py`)
- Thread-safe `EmergencyStopController` with an atomic cancellation flag.
- Listens for `ESC` key press via `CGEventTap` or `pynput`/`AppKit` local event monitor.
- Checked at every step of Bezier cursor motion (e.g. at 60Hz loop), mouse drags, and string typing.
- When triggered:
  - Immediately breaks active movement/typing loops.
  - Releases any held mouse buttons (left/right up) to prevent stuck drag states.
  - Clears tool execution queues.
  - Sets state to `STOPPED`.

### 3.3 Visible Cursor Dynamics (`macos/cursor.py`)
- Implements cubic Bezier curves with randomized slight control-point jitter (simulating human motor movement).
- Configurable easing (ease-in-out via sine/cubic curves).
- Trajectory interpolation calculates intermediate points based on target duration (default ~0.3s - 0.6s).
- Uses `CGWarpMousePosition` or `CGEventCreateMouseEvent(kCGEventMouseMoved)` with `CGEventPost(kCGHIDEventTap)`.
- Updates system cursor position visually and palpably.

### 3.4 Mouse Automation (`macos/mouse.py`)
- Native `CGEventCreateMouseEvent`:
  - `kCGEventLeftMouseDown`, `kCGEventLeftMouseUp`
  - `kCGEventRightMouseDown`, `kCGEventRightMouseUp`
  - `kCGEventLeftMouseDragged`
  - `kCGEventScrollWheel`
- Double click sets `kCGMouseEventClickState` to 2.
- Drag visibly steps the cursor while holding the left mouse button down, releasing at target.
- Verifies emergency stop between steps.

### 3.5 Keyboard Automation (`macos/keyboard.py`)
- Synthesizes `CGEventCreateKeyboardEvent` with virtual key codes for special keys (Return, Tab, Escape, Space, Arrow keys, etc.).
- Modifier flags for hotkeys: `kCGEventFlagMaskCommand`, `kCGEventFlagMaskShift`, `kCGEventFlagMaskAlternate`, `kCGEventFlagMaskControl`.
- Supports Unicode typing using `CGEventKeyboardSetUnicodeString`.
- Configurable human typing delay (default 15-30ms per character).

### 3.6 Application Lifecycle (`macos/apps.py`)
- Native `NSWorkspace.sharedWorkspace()`.
- App launch: `launchApplication_` or `openURL_options_configuration_error_`.
- App activate / focus: `runningApplications` search by bundle ID or localized name, calling `activateWithOptions:NSApplicationActivateIgnoringOtherApps`.
- App terminate: `terminate` or `forceTerminate`.
- Window queries: `CGWindowListCopyWindowInfo` filtering on on-screen windows and layer 0.

### 3.7 Accessibility Tree (`macos/accessibility.py`)
- Uses `AXUIElementCreateApplication(pid)` and `AXUIElementCopyAttributeValue`.
- Queries standard attributes: `kAXRoleAttribute`, `kAXTitleAttribute`, `kAXDescriptionAttribute`, `kAXPositionAttribute`, `kAXSizeAttribute`, `kAXChildrenAttribute`.
- Produces clean nested dictionaries of UI elements with their bounding boxes `(x, y, width, height)`.
- Structured error handling: if permissions are missing or an element cannot be read, returns `{"success": false, "error": "AXError: ..."}` without crashing.

### 3.8 Local Screenshots (`macos/screenshots.py`)
- `CGWindowListCreateImage` over display bounds or target window ID.
- Converts `CGImageRef` to local PIL image or writes PNG to local cache path (`~/.zoe/cache/` or project `temp/`).
- Retina downscaling/scaling metadata attached to screenshot output.
- No network transmission.

### 3.9 Local Action Logger (`macos/logger.py`)
- Logs timestamped actions to `logs/zoe.log` and console.
- Format: `[HH:MM:SS] ACTION_NAME key=value ...`
- Text masking option for sensitive typing.

### 3.10 Tool Registry (`tools/registry.py` & `tools/base.py`)
- Standardized `BaseTool` class.
- Each tool defines name, description, parameters schema (JSON schema compatible with future Ollama/llama.cpp/MLX tool calling).
- Standard return format:
  ```json
  {
    "success": true,
    "action": "click",
    "coordinates": [842, 611],
    "message": "Left click completed"
  }
  ```

---

## 4. 21-Point Acceptance Test Suite

The CLI tool will include an automated and interactive test suite covering:
1. Permissions check (Accessibility & Screen Recording)
2. Enumerate connected displays (Resolution, origin, Retina scale)
3. Convert coordinates across Retina / display bounds
4. Launch test application (e.g. TextEdit or Calculator)
5. Focus application
6. Close application
7. Smooth visible cursor movement
8. Left click
9. Right click
10. Double click
11. Drag
12. Scroll
13. Type text
14. Press individual keys
15. Execute keyboard shortcuts
16. Retrieve active application
17. Retrieve running applications
18. Retrieve application windows
19. Inspect Accessibility tree
20. Capture local screenshot
21. Trigger emergency stop (ESC) during action

---

## 5. Phase 2 Interface Handoff

In Phase 2, the local LLM will simply bind to `ToolRegistry.get_tools_schema()` and dispatch JSON tool calls directly to `ToolRegistry.execute(tool_name, arguments)`. No Phase 1 code will need rewrites.
