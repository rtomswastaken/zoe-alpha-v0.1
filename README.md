# Zoe

Zoe is a local AI computer assistant and desktop automation agent for macOS. It executes natural language commands by coordinating local language and vision models with native macOS APIs for screen inspection, keyboard and mouse control, voice interaction, and persistent memory.

## Overview

Zoe runs locally on device without external cloud API dependencies. Language reasoning and visual element localization are handled by local models served through Ollama, while all system interactions use native macOS frameworks (AppKit, Quartz, and Accessibility via PyObjC).

Key subsystems include:

- Computer use agent: Multi-step task execution loop (observe, think, act, verify) with built-in safety checks that block destructive commands.
- Native macOS control: Smooth Bezier cursor trajectories, mouse clicks, drags, keyboard typing, application lifecycle management, and in-memory screen capture.
- Local model routing: Integration with local Ollama instances running `qwen3:14b` for reasoning and tool calling, alongside `minicpm-v` for screen inspection.
- Voice pipeline: In-memory audio capture, VAD keyword wake word detection ("Zoe"), speech-to-text using `faster-whisper`, and text-to-speech using native `NSSpeechSynthesizer`.
- Display notch overlay: Borderless AppKit overlay anchored to the physical MacBook Pro display notch, providing visual state feedback and audio-reactive animations.
- Visual cursor subsystem: Independent, transparent click-through visual pointer and marker overlay that indicates intended targets without displacing the physical mouse pointer.
- OpenClicky bridge: Optional HTTP integration (`http://127.0.0.1:32123`) to delegate visual highlighting and guided interaction to the OpenClicky companion app.
- Persistent memory: Local SQLite database storing user preferences and task context across sessions.
- Emergency stop: Background Quartz event monitor that halts all actions, releases mouse drags, and resets state whenever the Escape key is pressed.

## Tech Stack

- Runtimes: Python 3.11+, macOS (Apple Silicon recommended)
- macOS APIs: PyObjC (`pyobjc-core`, `pyobjc-framework-Quartz`, `pyobjc-framework-Cocoa`, `pyobjc-framework-ApplicationServices`, `pyobjc-framework-CoreText`)
- Screen capture and image processing: Quartz, Pillow
- Model runtime: Ollama (`qwen3:14b`, `minicpm-v`)
- Voice: `sounddevice`, `numpy`, `faster-whisper`, `NSSpeechSynthesizer`
- Database: SQLite 3
- Configuration: PyYAML

## Requirements

- Operating System: macOS 12 Monterey or newer
- Architecture: Apple Silicon Mac (M-series processor with 16 GB+ unified memory recommended for running 14B parameter models locally)
- Python: Version 3.11 or newer
- Ollama: Installed and running locally (`http://127.0.0.1:11434`)
  ```bash
  ollama pull qwen3:14b
  ollama pull minicpm-v
  ```
- macOS Permissions:
  - Accessibility: Required to send mouse clicks, keystrokes, and read the accessibility tree.
  - Screen Recording: Required to capture screenshots for vision models.
  - Microphone: Required for voice input.

Permissions can be enabled in macOS System Settings under Privacy & Security.

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/rtomswastaken/zoe-alpha-v0.1.git
   cd zoe-alpha-v0.1
   ```

2. Create and activate a Python virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. Install base dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Install optional voice and test dependencies if needed:
   ```bash
   # Required for microphone recording and local speech-to-text:
   pip install numpy sounddevice faster-whisper

   # Required for running the test suite:
   pip install pytest
   ```

5. Verify system permissions:
   ```bash
   python -m zoe.main check-permissions
   ```

## Usage

Zoe can be executed via `python -m zoe.main <command>` or via the installed `zoe <command>` console script.

### Starting the Assistant

Launch the unified runtime (voice listening, wake word detection, notch UI, and agent loop):
```bash
python -m zoe.main start
```

Launch the interactive text and voice chat REPL:
```bash
python -m zoe.main chat
```

Start continuous voice listening:
```bash
python -m zoe.main listen
```

### Diagnostics and Status Checks

Check model connections and status:
```bash
python -m zoe.main model-status
python -m zoe.main vision-status
python -m zoe.main vision-test
```

Inspect the voice subsystem and microphone:
```bash
python -m zoe.main voice-status
python -m zoe.main voice-test
```

Test the MacBook notch overlay:
```bash
# Display physical notch geometry outline for visual alignment
python -m zoe.main notch-debug

# Cycle through animation states
python -m zoe.main notch-test

# Test audio-reactive glow with live microphone input
python -m zoe.main notch-test --live
```

Test the independent visual cursor overlay:
```bash
python -m zoe.main visual-cursor-test
python -m zoe.main visual-cursor-demo
```

Check the OpenClicky bridge:
```bash
python -m zoe.main openclicky-status
```

List registered agent tools:
```bash
python -m zoe.main list-tools
```

### Memory Management

Zoe stores persistent preferences and facts in a local SQLite database:

```bash
# Check memory database status
python -m zoe.main memory-status

# List all stored memories
python -m zoe.main memory-list

# Search stored memories
python -m zoe.main memory-search "browser"

# Delete a specific memory by key
python -m zoe.main memory-delete "<key>"

# Clear all stored memories
python -m zoe.main memory-clear --force
```

### Emergency Stop

A global emergency stop listener monitors the physical Escape key (keycode 53) via Quartz event APIs. Pressing Escape immediately aborts running cursor movements, cancels active agent tasks, releases mouse buttons, stops audio playback, and returns the assistant to idle state.

## Configuration

System configuration is defined in `zoe/config/config.yaml`. Key sections include:

- `model`: Ollama model name (`qwen3:14b`), endpoint (`http://127.0.0.1:11434`), temperature, and request timeout.
- `vision`: Vision model name (`minicpm-v`), confidence threshold, and debug overlay toggle.
- `agent`: Maximum tool calls per task and timeout limits.
- `cursor`: Trajectory duration, interpolation steps, easing function (`cubic_bezier`), and micro-jitter.
- `mouse`: Click delays and drag durations.
- `keyboard`: Inter-character typing delays and key press duration.
- `emergency`: Escape hotkey enable flag and poll interval.
- `voice`: Sample rate, wake word phrase (`zoe`), STT model (`base.en`), and TTS voice (`Samantha`).
- `ui.notch`: Notch animation and voice-reactive glow parameters.
- `openclicky`: Local bridge connection settings (`host: 127.0.0.1`, `port: 32123`).

### Environment Variables

The following environment variables can override configuration values:

- `ZOE_MEMORY_DB`: Path to the SQLite memory database (default: `data/zoe_memory.sqlite`).
- `ZOE_OPENCLICKY_ENABLED`: Enable or disable the OpenClicky bridge (`true` or `false`).
- `ZOE_OPENCLICKY_HOST`: Host for the OpenClicky service (default: `127.0.0.1`).
- `ZOE_OPENCLICKY_PORT`: Port for the OpenClicky service (default: `32123`).
- `ZOE_OPENCLICKY_TIMEOUT`: Bridge HTTP timeout in seconds (default: `2.0`).
- `ZOE_OPENCLICKY_TOKEN`: Optional authentication token for OpenClicky requests.

## Project Structure

```
zoe-alpha-v0.1/
├── pyproject.toml              # Project metadata, dependencies, entry points
├── requirements.txt            # Pinned base requirements
├── docs/                       # Specifications and integration documentation
├── tests/                      # Automated unit and integration test suite
└── zoe/                        # Core package
    ├── agent/                  # Task execution loop, planning, safety guards, state
    ├── config/                 # YAML configuration parser and settings
    ├── integrations/           # External service bridges (OpenClicky)
    ├── macos/                  # PyObjC wrappers (display, cursor, mouse, keyboard, emergency)
    ├── memory/                 # SQLite storage, schema, and retrieval manager
    ├── models/                 # Ollama LLM and vision model adapters
    ├── tools/                  # Tool definitions and central registry
    ├── ui/                     # AppKit MacBook notch overlay and animations
    ├── visual/                 # Native visual cursor and marker overlay subsystem
    ├── voice/                  # Audio recording, wake word detector, STT, and TTS
    ├── cli.py                  # CLI command implementations and acceptance suite
    ├── main.py                 # CLI entry point
    └── runtime.py              # Unified assistant orchestrator
```

## Testing

The project includes unit, integration, and macOS acceptance test suites.

```bash
# Run automated test suite with pytest
pytest tests/ -v

# Run the 21-point live macOS acceptance suite
python -m zoe.main test-all
```

The acceptance suite verifies connected displays, Retina coordinate translation, application lifecycle controls, mouse and keyboard events, in-memory screenshot capture, and emergency stop triggers.

## Current Status and Limitations

- Development Stage: Alpha (`v0.1.0`). Core macOS automation, local reasoning, and UI overlays are functional, but edge cases in third-party application accessibility structures are expected.
- Platform Bound: Requires macOS due to hard dependencies on Quartz, Cocoa, and ApplicationServices. Linux and Windows are not supported.
- Hardware Demands: Running local 14B reasoning models and vision models concurrently requires sufficient Apple Silicon unified memory (16 GB minimum, 32 GB recommended).
- Display Notch Geometry: Physical notch detection uses macOS display auxiliary areas; on non-notch external displays, the overlay falls back to the top-center edge of the screen.
