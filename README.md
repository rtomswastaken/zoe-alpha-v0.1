# Zoe (Z-O-E) — Personal Local AI Computer Assistant for macOS

> **100% Local • Private • Apple Silicon Native • On-Device Voice & Vision**

Zoe is a personal, private, on-device AI voice assistant and computer-use agent for macOS. Zoe listens for her wake word, understands natural-language voice commands, visually inspects your Mac screen, moves the physical cursor, interacts with desktop applications, and provides ambient visual feedback through an animated gradient glow around your MacBook Pro display notch.

Everything runs **100% locally on your Mac** with zero cloud APIs, zero telemetry, and zero data leaving your device.

---

## 1. Complete Architecture

```
                         ZOE
              ┌─────────────────────┐
              │     MacBook Notch   │
              │    Reactive UI      │
              └──────────┬──────────┘
                         │
                     "Zoe..."
                         │
                         ↓
                 Local Wake Word (VAD + Keyword)
                         ↓
                 Local STT (faster-whisper)
                         ↓
                 Qwen3:14b (via Ollama)
                         ↓
                ┌────────┴────────┐
                ↓                 ↓
          macOS Tools         MiniCPM-V (Local Vision)
          (PyObjC/Quartz)     (via Ollama)
                ↓                 ↓
                └────────┬────────┘
                         ↓
               Computer Use Loop
            (Plan → Act → Observe)
                         ↓
                   Verification
                         ↓
              Local Memory (SQLite)
                         ↓
                 Local TTS (NSSpeech)
                         ↓
                       User
```

### Core Architecture Highlights
1. **100% Local Execution**: No OpenAI, Anthropic, Google, or third-party cloud APIs. Offline-capable.
2. **Apple Silicon Hardware Acceleration**: Metal/MPS-accelerated LLM reasoning (Qwen3:14b), on-device vision (MiniCPM-V), and int8-quantized STT (faster-whisper).
3. **Physical Screen Control**: Smooth, visible cubic-Bezier cursor movement, native Quartz mouse/keyboard events, and multi-monitor Retina coordinate mapping.
4. **MacBook Notch Glow Interface**: Native PyObjC/Cocoa non-activating borderless overlay anchored to physical MacBook Pro display notch with audio-reactive gradient pulses.
5. **Episodic & Persistent Memory**: Local SQLite database storing user preferences and task context without ballooning LLM token limits.
6. **Safety & Emergency Controls**: Global physical **ESC** hotkey stops all actions, releases mouse drag, halts audio playback, and resets Zoe to IDLE immediately. Destructive commands (e.g. `rm -rf`, file wipe) are blocked by default.

---

## 2. Requirements & Prerequisites

- **Hardware**: Apple Silicon Mac (M1 Pro / M1 Max / M2 / M3 / M4, 32 GB unified memory recommended)
- **Operating System**: macOS 12 Monterey or newer (tested on macOS 15+ Sequoia)
- **Local Services**:
  - [Ollama](https://ollama.com) running locally (`http://127.0.0.1:11434`)
  - Models pulled locally:
    ```bash
    ollama pull qwen3:14b
    ollama pull minicpm-v
    ```
- **Python**: Python 3.10+ (tested with 3.14 arm64)

---

## 3. Installation

1. **Clone the repository**:
   ```bash
   git clone <repository_url>
   cd zoe-ai
   ```

2. **Create and activate virtual environment**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Grant macOS Permissions**:
   Zoe requires two permissions in macOS System Settings:
   - **Accessibility**: System Settings → Privacy & Security → Accessibility → Enable your Terminal / IDE.
   - **Screen Recording**: System Settings → Privacy & Security → Screen Recording → Enable your Terminal / IDE.
   - **Microphone**: Granted on first launch for voice input.

   Verify permissions at any time:
   ```bash
   python -m zoe.main check-permissions
   ```

---

## 4. Quickstart & Running Zoe

### Launch Unified Assistant Runtime
Starts the complete system: Wake Word detection ("Zoe"), ambient Notch UI, local STT/TTS, and reasoning agent:
```bash
python -m zoe.main start
```

### Voice Status & Diagnostics
Check the health of all local audio, speech, and notch components:
```bash
python -m zoe.main voice-status
python -m zoe.main voice-test
python -m zoe.main notch-test
```

### Continuous Voice Listening
Listen continuously with the ambient MacBook notch glow:
```bash
python -m zoe.main listen
```

### Text / Voice Interactive REPL
```bash
python -m zoe.main chat
```

### Memory Management
```bash
python -m zoe.main memory-status
python -m zoe.main memory-list
python -m zoe.main memory-search "browser"
python -m zoe.main memory-delete "<key>"
python -m zoe.main memory-clear
```

---

## 5. Voice Interaction & Wake Word

- **Wake Phrase**: Say **"Zoe"** or **"Hey Zoe"**.
- **States**:
  - `IDLE`: Invisible notch overlay, listening for wake word.
  - `LISTENING`: Subtle expanding notch gradient, capturing command audio.
  - `THINKING`: Slow flowing gradient, local STT & Qwen3:14b reasoning.
  - `ACTING`: Flowing pulse while operating Mac tools and vision.
  - `SPEAKING`: Voice-reactive notch glow synchronized with local TTS audio amplitude.
- **Interruption**:
  - Say **"Zoe, stop"** or **"stop"** at any point.
  - Press **ESC** at any time to immediately abort all movement, speech, and planning.

---

## 6. Project Architecture

```
zoe/
├── config/                  # Configuration loader & config.yaml
├── macos/                   # macOS foundation layer (PyObjC, Quartz, AppKit)
│   ├── display.py           # Multi-monitor & Retina coordinate mapping
│   ├── cursor.py            # Smooth Bezier visible cursor trajectories
│   ├── mouse.py             # Native mouse clicks, scrolls, drags
│   ├── keyboard.py          # Native unicode keystrokes and hotkeys
│   ├── apps.py              # NSWorkspace app lifecycle & window geometry
│   ├── accessibility.py     # Native AXUIElement accessibility tree traversal
│   ├── screenshots.py       # High-speed in-memory Quartz screen capture
│   ├── emergency.py         # Global ESC emergency stop controller
│   ├── logger.py            # Local structured privacy logger
│   └── permissions.py       # macOS permission inspectors
├── models/                  # Local model provider layer (Ollama)
│   ├── base.py              # LocalModel and ModelResponse interfaces
│   ├── ollama.py            # Local Ollama client (num_ctx=4096, think=False)
│   ├── factory.py           # LLM model factory
│   └── vision_factory.py    # MiniCPM-V vision model factory
├── tools/                   # Safe tool registry & structured tool schemas
│   ├── registry.py          # Central registry with JSON-schema export
│   ├── computer.py          # Mouse, cursor, and keyboard tool implementations
│   ├── applications.py      # App lifecycle tool implementations
│   └── vision.py            # find_on_screen and inspect_screen tools
├── agent/                   # Advanced computer use agent
│   ├── agent.py             # ZoeAgent coordinator
│   ├── loop.py              # Observe-Think-Act-Verify agent loop
│   ├── plan.py              # Multi-step task planning
│   ├── history.py           # Structured action history & repetition loop detector
│   ├── safety.py            # Destructive task safety guards
│   ├── prompts.py           # Zoe system prompt & memory injection
│   └── state.py             # Episodic task state tracking
├── voice/                   # 100% Local voice subsystem
│   ├── audio.py             # In-memory audio recording & amplitude analysis
│   ├── wake_word.py         # Local VAD keyword wake word detector ("Zoe")
│   ├── stt.py               # faster-whisper local STT (base.en int8)
│   ├── tts.py               # Native NSSpeechSynthesizer TTS
│   ├── state.py             # Thread-safe VoiceState manager
│   └── pipeline.py          # Full end-to-end voice pipeline
├── ui/                      # Native MacBook Notch UI
│   ├── notch.py             # PyObjC borderless overlay & notch geometry
│   ├── animation.py         # 30fps voice-reactive gradient animator
│   └── state.py             # UI state bridge
├── memory/                  # Local SQLite memory
│   ├── database.py          # Local SQLite connection & migrations
│   ├── models.py            # MemoryItem & MemoryType definitions
│   ├── store.py             # CRUD operations & category indexing
│   ├── retrieval.py         # Task-relevant salience filtering
│   └── manager.py           # High-level memory facade & directive parser
├── runtime.py               # Unified Zoe assistant runtime
├── cli.py                   # Comprehensive CLI command suite
└── main.py                  # CLI entrypoint
```

---

## 7. Testing

Zoe features full automated test coverage across all seven phases:

```bash
# Run complete test suite (77 automated unit/integration tests)
.venv/bin/pytest tests/ -v

# Run the 21-point macOS acceptance suite (live display, cursor, windows)
python -m zoe.main test-all
```

---

## 8. Privacy & Security Guarantees

- **Zero Cloud Network Traffic**: No external HTTP requests are made. Ollama communicates strictly over `127.0.0.1`.
- **In-Memory Audio**: Microphone recordings remain strictly in memory and are discarded after transcription.
- **Local Screenshots**: Screen captures are processed in memory and cached locally under `cache/screenshots/`.
- **No LLM Shell Access**: The agent cannot execute arbitrary bash or python code; all actions must route through registered, typed tools.
- **Physical ESC Override**: Hardware keyboard override always takes precedence over software logic.
