"""Unit tests for local TTS engine."""

import pytest
from zoe.voice.tts import NSSpeechTTS, BaseTTS, get_tts


def test_tts_singleton_and_type():
    tts = get_tts()
    assert isinstance(tts, BaseTTS)
    assert isinstance(tts, NSSpeechTTS)


def test_tts_voice_enumeration():
    tts = get_tts()
    voices = tts.get_voices()
    assert len(voices) > 0
    # Common standard macOS voices
    voice_names_lower = [v.lower() for v in voices]
    assert any("samantha" in v or "alex" in v or "ava" in v for v in voice_names_lower)


def test_tts_stop_interruption():
    tts = NSSpeechTTS(rate=200)
    # Start speaking long text without blocking
    tts.speak("This is a long test sentence designed to test speech interruption.", wait=False)
    # Immediately trigger stop
    tts.stop()
    assert tts.is_speaking() is False
