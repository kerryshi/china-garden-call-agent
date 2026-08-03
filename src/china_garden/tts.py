"""Local neural TTS: Kokoro-82M via kokoro-onnx.

Kokoro-82M is Apache-2.0 (weights included) - safe to front a commercial
product, unlike Fish/OpenAudio whose weights are CC-BY-NC. Runs faster than
real time on Apple Silicon CPU; fully offline once the model files are local.

Model files (one-time fetch, see scripts/fetch-tts.sh):
  kokoro-v1.0.onnx + voices-v1.0.bin -> ~/.cache/china-garden-tts/
Override the directory with CG_TTS_DIR.
"""

from __future__ import annotations

import io
import os
import wave
from pathlib import Path

MODEL_FILE = "kokoro-v1.0.onnx"
VOICES_FILE = "voices-v1.0.bin"
VOICE_EN = "af_heart"


def default_dir() -> Path:
    return Path(os.environ.get("CG_TTS_DIR",
                               Path.home() / ".cache" / "china-garden-tts"))


class KokoroEngine:
    """Thin wrapper: text in, WAV bytes out. English voices only - Chinese
    replies use the client's system voice (Kokoro's zh pipeline isn't demo-
    grade yet)."""

    def __init__(self, kokoro):
        self._kokoro = kokoro

    @classmethod
    def try_load(cls, directory: Path | None = None) -> KokoroEngine | None:
        d = directory or default_dir()
        model, voices = d / MODEL_FILE, d / VOICES_FILE
        if not (model.exists() and voices.exists()):
            return None
        try:
            from kokoro_onnx import Kokoro
        except ImportError:
            return None
        return cls(Kokoro(str(model), str(voices)))

    def synthesize(self, text: str, voice: str = VOICE_EN, speed: float = 1.0) -> bytes:
        import numpy as np

        samples, sample_rate = self._kokoro.create(
            text, voice=voice, speed=speed, lang="en-us")
        pcm = (np.clip(samples, -1.0, 1.0) * 32767).astype(np.int16)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sample_rate)
            w.writeframes(pcm.tobytes())
        return buf.getvalue()
