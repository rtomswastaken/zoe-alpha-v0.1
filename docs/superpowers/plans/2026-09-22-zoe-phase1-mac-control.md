# Zoe Phase 1: Mac Control Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a 100% local, native macOS computer-control foundation using PyObjC, Quartz/CoreGraphics, and Accessibility APIs with visible smooth cursor movement, emergency-stop fail-safe, structured results, Retina display handling, and a 21-point acceptance test suite.

**Architecture:** Native Apple Silicon macOS control layer (`zoe/macos/`) decoupled from tool definitions (`zoe/tools/`), with an atomic emergency stop controller, local action logger, and JSON-serializable tool contracts ready for Phase 2 local LLM integration.

**Tech Stack:** Python 3.14, `pyobjc-framework-Quartz`, `pyobjc-framework-ApplicationServices`, `pyobjc-framework-Cocoa`, `pillow`, `pyyaml`. Zero PyAutoGUI, zero cloud.

**Spec:** [docs/superpowers/specs/2026-09-22-zoe-phase1-mac-control-design.md](../specs/2026-09-22-zoe-phase1-mac-control-design.md)

## Global Constraints

- **Platform:** macOS on Apple Silicon (`arm64`), Python 3.14 virtual environment (`.venv`).
- **Dependencies:** Exclusively native macOS bindings (`pyobjc-framework-Quartz`, `pyobjc-framework-ApplicationServices`, `pyobjc-framework-Cocoa`), `pillow`, and `pyyaml`. No PyAutoGUI.
- **Privacy & Local Only:** Zero external network calls. Zero telemetry. Zero remote services.
- **Observability:** Cursor movements must be visibly animated using smooth curves; no instant teleportation.
- **Safety:** Global emergency-stop (ESC) halts in-flight operations and drops queued actions. Destructive actions fail safely.
- **Structured Outputs:** All tools return `{"success": bool, "action": str, ...}` dictionaries.

---

## Task Structure & Decomposition

### Task 1: Project Foundation, Config, and Logger
**Files:**
- Create: `zoe/__init__.py`
- Create: `zoe/config/__init__.py`
- Create: `zoe/config/config.yaml`
- Create: `zoe/config/settings.py`
- Create: `zoe/macos/__init__.py`
- Create: `zoe/macos/logger.py`
- Test: `tests/test_config_logger.py`

**Interfaces:**
- Produces: `Config` singleton, `zoe_logger.log_action(action: str, **kwargs)`, `zoe_logger.get_history()`

### Task 2: Emergency Stop System
**Files:**
- Create: `zoe/macos/emergency.py`
- Test: `tests/test_emergency.py`

**Interfaces:**
- Produces: `EmergencyStopController.is_stopped()`, `EmergencyStopController.trigger()`, `EmergencyStopController.reset()`, `EmergencyStopController.check_and_raise()`, `EmergencyStopTriggeredException`

### Task 3: Display Coordinates & Retina Multi-Monitor
**Files:**
- Create: `zoe/macos/display.py`
- Test: `tests/test_display.py`

**Interfaces:**
- Produces: `DisplayManager.get_displays()`, `DisplayManager.get_main_display()`, `DisplayManager.point_to_pixel(x, y)`, `DisplayManager.pixel_to_point(x, y)`, `DisplayManager.validate_coordinates(x, y)`

### Task 4: Permissions Verifier
**Files:**
- Create: `zoe/macos/permissions.py`
- Test: `tests/test_permissions.py`

**Interfaces:**
- Produces: `check_accessibility_permission() -> bool`, `check_screen_recording_permission() -> bool`, `get_permission_status() -> dict`

### Task 5: Visible Smooth Cursor Dynamics
**Files:**
- Create: `zoe/macos/cursor.py`
- Test: `tests/test_cursor.py`

**Interfaces:**
- Produces: `get_cursor_position() -> tuple[float, float]`, `move_cursor_smooth(x, y, duration=0.4, steps=50)`

### Task 6: Mouse Automation (Click, Double Click, Right Click, Drag, Scroll)
**Files:**
- Create: `zoe/macos/mouse.py`
- Test: `tests/test_mouse.py`

**Interfaces:**
- Produces: `mouse_click(x=None, y=None, button="left")`, `mouse_double_click(x=None, y=None)`, `mouse_right_click(x=None, y=None)`, `mouse_drag(start_x, start_y, end_x, end_y, duration=0.5)`, `mouse_scroll(vertical=0, horizontal=0)`

### Task 7: Keyboard Automation & Hotkeys
**Files:**
- Create: `zoe/macos/keyboard.py`
- Test: `tests/test_keyboard.py`

**Interfaces:**
- Produces: `press_key(key: str)`, `key_down(key: str)`, `key_up(key: str)`, `hotkey(*keys)`, `type_text(text: str, delay=0.02)`

### Task 8: Application Lifecycle & Window Management
**Files:**
- Create: `zoe/macos/apps.py`
- Test: `tests/test_apps.py`

**Interfaces:**
- Produces: `launch_app(name_or_bundle: str) -> dict`, `activate_app(name: str) -> dict`, `quit_app(name: str, force=False) -> dict`, `get_active_app() -> dict`, `get_running_apps() -> list[dict]`, `get_windows() -> list[dict]`

### Task 9: Accessibility Tree Traversal
**Files:**
- Create: `zoe/macos/accessibility.py`
- Test: `tests/test_accessibility.py`

**Interfaces:**
- Produces: `get_app_accessibility_tree(app_name: str, max_depth=3) -> dict`, `find_elements_by_role(tree: dict, role: str) -> list[dict]`, `find_element_by_title(tree: dict, title: str) -> dict | None`

### Task 10: Local Screenshots & Retina Handling
**Files:**
- Create: `zoe/macos/screenshots.py`
- Test: `tests/test_screenshots.py`

**Interfaces:**
- Produces: `capture_screen(display_id=None, save_path=None) -> dict`, `capture_window(window_id: int, save_path=None) -> dict`

### Task 11: Structured Tool Registry
**Files:**
- Create: `zoe/tools/__init__.py`
- Create: `zoe/tools/base.py`
- Create: `zoe/tools/registry.py`
- Create: `zoe/tools/computer.py`
- Create: `zoe/tools/applications.py`
- Test: `tests/test_tools.py`

**Interfaces:**
- Produces: `ToolResult`, `BaseTool`, `ToolRegistry.register()`, `ToolRegistry.execute(name, **kwargs)`, `ToolRegistry.get_schema_definitions()`

### Task 12: CLI Runner & 21-Point Acceptance Test Suite
**Files:**
- Create: `zoe/cli.py`
- Create: `zoe/main.py`
- Test: `tests/test_acceptance_suite.py`

**Interfaces:**
- Produces: CLI commands `python -m zoe.main check-permissions`, `python -m zoe.main test-all`, `python -m zoe.main interactive`

---

## Verification Plan

### Automated Tests
Run pytest in `.venv`:
```bash
.venv/bin/python -m pytest tests/ -v
```

### 21-Point Acceptance Suite
Execute acceptance runner:
```bash
.venv/bin/python -m zoe.main test-all
```
Verifies:
1. Permissions check
2. Display enumeration
3. Coordinate conversion
4. Launch app (TextEdit)
5. Focus app
6. Close app
7. Smooth cursor movement
8. Left click
9. Right click
10. Double click
11. Drag
12. Scroll
13. Type text
14. Press key
15. Hotkey
16. Get active app
17. Get running apps
18. Get windows
19. Accessibility tree
20. Capture screenshot
21. Emergency stop trigger & recovery
