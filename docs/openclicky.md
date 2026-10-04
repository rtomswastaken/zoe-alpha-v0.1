# OpenClicky Visual Control Layer Integration for Zoe

This document details the architecture, configuration, coordinate system, and usage of the OpenClicky visual interaction layer inside Zoe.

---

## 1. What OpenClicky Does

[OpenClicky](https://github.com/jasonkneen/openclicky) is a native macOS companion app that provides a non-invasive visual overlay.

When integrated with Zoe:
- **Visual Cursor Choreography**: OpenClicky detaches its animated pointer, glides to a target UI element, presents a contextual speech bubble, and returns to rest without warping or capturing the user's actual macOS mouse cursor.
- **Multi-Target Highlighting**: Displays multiple simultaneous color-accented markers when explaining multiple options or walking through a workflow.
- **Contextual Captions**: Displays floating text labels near UI controls or mouse positions.
- **Text-to-Speech (TTS)**: Plays brief instructional voice prompts without interfering with Zoe's native voice pipeline.
- **Clean Responsibilities**:
  - **Zoe Notch Overlay**: Ambient wake-word listening, thinking states, assistant glow, audio activity, status notifications.
  - **OpenClicky Overlay**: Pointer animation, screen interaction feedback, UI element guidance.

---

## 2. Architecture

```text
                           ┌─────────────────────────┐
                           │       USER / VOICE      │
                           └────────────┬────────────┘
                                        │
                               ┌────────▼────────┐
                               │ Wake Word / STT │
                               └────────┬────────┘
                                        │
                                        ▼
                         ┌─────────────────────────────┐
                         │          ZOE BRAIN          │
                         │  • Local LLM (Ollama)       │
                         │  • Observe-Think-Act Loop   │
                         │  • SQLite Memory            │
                         └──────────────┬──────────────┘
                                        │
                         ┌──────────────┴──────────────┐
                         ▼                             ▼
               ┌──────────────────┐          ┌───────────────────┐
               │  Tool Registry   │          │   Vision Router   │
               └─────────┬────────┘          └─────────┬─────────┘
                         │                             │
        ┌────────────────┼────────────────┐            ▼
        ▼                ▼                ▼     ┌────────────────┐
   macOS Control    App & Files      MCP Adapter│ Local Vision   │
   • PyObjC / CGEvent                           │ MiniCPM-V      │
   • Accessibility                              └──────┬─────────┘
   • Notch UI                                          │
        │                                              ▼
        │                                    Vision Coordinates
        │                                              │
        │                                              ▼
        │                                     Coordinate Transformer
        │                                     (Retina & AppKit Y-flip)
        │                                              │
        └───────────────────────┬──────────────────────┘
                                │
                                ▼
                   ┌─────────────────────────┐
                   │    OpenClicky Bridge    │
                   │  http://127.0.0.1:32123 │
                   └────────────┬────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
┌───────────────┐       ┌───────────────┐       ┌───────────────┐
│ Primary Cursor│       │ Multi-Cursors │       │ Visual Caption│
│ Choreography  │       │ & Markers     │       │ Overlay       │
└───────────────┘       └───────────────┘       └───────────────┘
```

---

## 3. Installation of OpenClicky

1. Clone or download OpenClicky:
   ```bash
   git clone https://github.com/jasonkneen/openclicky.git
   cd openclicky
   ```
2. Open in Xcode:
   ```bash
   open cursor-buddy.xcodeproj
   ```
3. Set your local developer team under Target Signing, build and run (`Cmd+R`).
4. Ensure Accessibility and Screen Recording permissions are granted to OpenClicky in **System Settings > Privacy & Security**.
5. OpenClicky will automatically bind its local bridge to:
   ```text
   http://127.0.0.1:32123
   ```

---

## 4. How Zoe Connects

Zoe communicates with OpenClicky using a dedicated loopback HTTP client:
- **Base Endpoint**: `http://127.0.0.1:32123`
- **Transport**: JSON over HTTP/1.1 with strict timeouts (default 2.0s).
- **Security Check**: Enforces loopback addresses only (`127.0.0.1`, `localhost`, `::1`).
- **Bridge Token**: Optional authentication header `x-openclicky-token` / `Authorization: Bearer <token>`.
- **Fault-Tolerant**: If OpenClicky is not running, Zoe gracefully marks the visual bridge as offline and proceeds with standard native actions.

---

## 5. Configuration

Configured in `zoe/config/config.yaml`:

```yaml
openclicky:
  enabled: true
  host: "127.0.0.1"
  port: 32123
  timeout: 2.0
  token: ""
```

### Environment Variable Overrides

Any configuration value can be overridden via environment variables:

| Environment Variable | Description | Default |
|----------------------|-------------|---------|
| `ZOE_OPENCLICKY_ENABLED` | Enable or disable the integration (`true`/`false`) | `true` |
| `ZOE_OPENCLICKY_HOST` | Local host to connect to (must be loopback) | `127.0.0.1` |
| `ZOE_OPENCLICKY_PORT` | Port number | `32123` |
| `ZOE_OPENCLICKY_TIMEOUT` | Timeout in seconds for HTTP requests | `2.0` |
| `ZOE_OPENCLICKY_TOKEN` | Optional bridge token | `""` |

---

## 6. Available Tools in Zoe

All OpenClicky capabilities are exposed through Zoe's standard `BaseTool` registry:

| Tool Name | Parameters | Description |
|-----------|------------|-------------|
| `openclicky_health` | None | Checks connectivity, latency, and registered capabilities. |
| `openclicky_screenshot` | `focused: bool` | Captures screenshots via OpenClicky with display frame metadata. |
| `openclicky_point` | `x, y, caption, duration_ms, mode, accent_hex, travel_ms, coordinate_space` | Glides the OpenClicky pointer to screen coordinates. Mode can be `primary` or `secondary`. |
| `openclicky_multi_point` | `cursors: List, duration_ms, coordinate_space` | Shows multiple simultaneous pointers for multi-target explanation. |
| `openclicky_caption` | `text, x, y, duration_ms, accent_hex, coordinate_space` | Shows a floating text caption bubble. |
| `openclicky_speak` | `text, interrupt` | Speaks text through OpenClicky TTS without entering voice mode. |
| `openclicky_clear` | None | Clears active cursors and captions from the overlay. |
| `openclicky_guide` | `target, caption, app_name, duration_ms` | End-to-end guidance: Accessibility + Vision search -> OpenClicky visual pointer. |

---

## 7. Canonical Coordinate System

Retina Mac displays feature different physical pixel densities (e.g. 2x backing scale) and macOS uses two distinct coordinate systems:
1. **Quartz / CoreGraphics** (Used by Zoe's mouse, cursor, and CGEvent):
   - Origin `(0, 0)` is at the **top-left** of the primary screen.
   - Y increases downwards.
2. **AppKit / Cocoa** (Used by OpenClicky's bridge and NSScreen):
   - Origin `(0, 0)` is at the **bottom-left** of the primary screen.
   - Y increases upwards.

### Transformation Pipeline

```text
Vision Coordinates (vx, vy)
          │
          ▼
Screenshot Pixel Space (px, py)
          │
          ▼
Retina Scale (pixels / backing_scale_factor)
          │
          ▼
Multi-Monitor Origin Offset
          │
          ▼
macOS Quartz Logical Points (qx, qy)
          │
          ▼
AppKit Invariant:
  openclicky_x = qx
  openclicky_y = primary_height - qy
          │
          ▼
OpenClicky Bridge (/cursor, /caption)
```

The mathematical invariant `openclicky_y = primary_height - qy` holds universally across all multi-monitor setups, including arrangements where monitors are placed above (negative Quartz Y, AppKit Y > `primary_height`) or below (positive Quartz Y, negative AppKit Y).

---

## 8. Visual Interaction Modes

Zoe implements three interaction modes:

### MODE 1 — Explain
- **User Prompt**: *"Where is the Downloads folder?"*
- **Execution**: Zoe locates the element via Accessibility or local vision, converts coordinates, and invokes `openclicky_point` with caption `"Downloads"`.
- **Physical Mouse**: Completely untouched.

### MODE 2 — Guide
- **User Prompt**: *"Show me where I should click to change Wi-Fi."*
- **Execution**: Zoe locates the element, displays the animated OpenClicky pointer with an accent ring and instruction bubble (`"Click here"`).
- **Physical Mouse**: Untouched.

### MODE 3 — Act
- **User Prompt**: *"Click the Wi-Fi settings."*
- **Execution**:
  1. Preferred: Accessibility API -> Locate element -> Execute click via Quartz CGEvent.
  2. Fallback: Vision model -> Locate element -> Coordinate conversion -> Click via Quartz CGEvent.
- **OpenClicky Role**: Provides visual confirmation feedback at the target location, while Zoe's native macOS automation performs the real click.

---

## 9. Security Model

1. **Strict Local Loopback**: All network requests are strictly bound to `127.0.0.1` or `localhost`. Binding to `0.0.0.0` or non-local IP addresses is rejected with `OpenClickySecurityError`.
2. **Zero Cloud Uploads**: Screenshots and coordinates remain 100% on the local machine.
3. **No Credential Logging**: Sensitive data (passwords, tokens, screenshot binary data) are masked or omitted from logs.

---

## 10. Troubleshooting

### Check Bridge Status

Run the Zoe CLI command:
```bash
zoe openclicky-status
```

Output when connected:
```text
ZOE OPENCLICKY VISUAL SUBSYSTEM
────────────────────────────────────
OpenClicky: CONNECTED
Bridge:     http://127.0.0.1:32123
Latency:    8.2ms
Tools:      8
────────────────────────────────────
✓ OpenClicky visual control bridge is online.
```

Output when OpenClicky is not running:
```text
ZOE OPENCLICKY VISUAL SUBSYSTEM
────────────────────────────────────
OpenClicky: DISCONNECTED
Bridge:     http://127.0.0.1:32123
Reason:     Bridge is offline (Connection refused).
────────────────────────────────────
ℹ OpenClicky bridge is currently not reachable.
```

### Common Issues

1. **Connection Refused**: OpenClicky is not running. Launch OpenClicky from Xcode or your Applications folder.
2. **Unauthorized (401)**: OpenClicky has `OPENCLICKY_BRIDGE_TOKEN` configured. Set `ZOE_OPENCLICKY_TOKEN=<your_token>` in your environment or `config.yaml`.
3. **Screen Coordinates Mismatch**: Ensure your display arrangement in macOS System Settings hasn't changed without Zoe re-enumerating displays.

---

## 11. How to Disable OpenClicky

To disable the OpenClicky integration:
- Edit `zoe/config/config.yaml`:
  ```yaml
  openclicky:
    enabled: false
  ```
- Or set the environment variable:
  ```bash
  export ZOE_OPENCLICKY_ENABLED=false
  ```
Zoe will continue operating as normal, using its native macOS controls and Notch overlay.
