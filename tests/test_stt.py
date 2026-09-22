"""Unit tests for local STT engine and AudioAnalyzer."""

import numpy as np
import pytest
from zoe.voice.audio import AudioAnalyzer
from zoe.voice.stt import BaseSTT, FasterWhisperSTT, get_stt


def test_audio_analyzer_rms_and_pitch():
    analyzer = AudioAnalyzer(sample_rate=16000)

    # Test silence
    silence = np.zeros(512, dtype=np.float32)
    rms, pitch = analyzer.process_chunk(silence)
    assert rms == 0.0

    # Test pure 440Hz sine wave
    t = np.linspace(0, 512 / 16000, 512, endpoint=False)
    tone = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    for _ in range(5):
        rms, pitch = analyzer.process_chunk(tone)
    assert rms > 0.05
    assert 350.0 <= pitch <= 500.0


def test_stt_singleton_and_type():
    stt = get_stt()
    assert isinstance(stt, BaseSTT)
    assert isinstance(stt, FasterWhisperSTT)
    assert stt.is_available() is True


def test_stt_transcribe_empty():
    stt = get_stt()
    empty = np.zeros(0, dtype=np.float32)
    result = stt.transcribe(empty)
    assert result == ""
