# OpenClicky Integration Module for Zoe

This module provides Zoe's integration with **OpenClicky**, an optional local macOS companion app that renders smooth visual pointer choreography, contextual captions, multi-marker highlights, and text-to-speech.

## Philosophy

- **Zoe remains the brain**: Local LLM reasoning, planning, safety guards, memory, and native macOS execution stay in Zoe.
- **OpenClicky is the visual interaction layer**: Zoe can point to UI elements without warping the user's real mouse cursor.
- **100% Local & Isolated**: Zoe communicates with OpenClicky exclusively over local loopback (`http://127.0.0.1:32123`). If OpenClicky is closed or unavailable, Zoe continues functioning normally without errors or degradation.

## Directory Structure

```text
zoe/integrations/openclicky/
├── __init__.py           # Package exports and public interface
├── client.py             # OpenClickyClient (HTTP + timeouts + security)
├── coordinates.py        # Canonical Retina & AppKit coordinate pipeline
├── health.py             # Non-blocking health checks and status diagnostics
├── mcp_adapter.py        # Dynamic MCP tool discovery and wrapper
├── models.py             # Typed dataclasses and custom exceptions
├── tools.py              # BaseTool implementations registered with ToolRegistry
├── visual_modes.py       # Explain, Guide, and Act interaction modes
└── README.md             # This document
```

## Available Tools

- `openclicky_health`: Check bridge connection and latency.
- `openclicky_screenshot`: Capture screens via OpenClicky with AppKit display frames.
- `openclicky_point`: Smoothly point at screen coordinates with optional caption.
- `openclicky_multi_point`: Display multiple simultaneous marker cues.
- `openclicky_caption`: Display a floating visual caption bubble.
- `openclicky_speak`: Speak brief audio instructions via OpenClicky TTS.
- `openclicky_clear`: Clear active overlays.
- `openclicky_guide`: End-to-end visual guidance (Accessibility + Vision -> OpenClicky pointer).
