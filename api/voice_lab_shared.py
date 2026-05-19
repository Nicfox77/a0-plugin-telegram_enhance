import os
import json
import base64
import tempfile
import subprocess
import threading
from pathlib import Path

from helpers.print_style import PrintStyle


PLUGIN_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = PLUGIN_DIR / "models"
VOICES_PATH = MODELS_DIR / "voices_custom.npz"
MODEL_PATH = MODELS_DIR / "kokoro.onnx"
BLENDS_JSON = PLUGIN_DIR / "saved_blends.json"

_lock = threading.Lock()
_kokoro_instance = None


def get_kokoro():
    """Lazy-load and cache the Kokoro model (thread-safe)."""
    global _kokoro_instance
    if _kokoro_instance is None:
        try:
            from kokoro_onnx import Kokoro
        except ImportError:
            raise ImportError(
                "kokoro-onnx is required. Install with: pip install kokoro-onnx onnxruntime"
            )
        PrintStyle.info(f"Voice Lab: loading Kokoro model from {MODEL_PATH}...")
        _kokoro_instance = Kokoro(str(MODEL_PATH), str(VOICES_PATH))
        PrintStyle.info("Voice Lab: Kokoro model loaded.")
    return _kokoro_instance


def load_voices():
    """Load voice arrays from the npz file."""
    import numpy as np
    return dict(np.load(str(VOICES_PATH)))


def compute_blend(voices_dict, blend_spec):
    """Compute a weighted blend from a list of {name, weight} dicts."""
    total_weight = sum(item["weight"] for item in blend_spec)
    if total_weight == 0:
        raise ValueError("Total weight cannot be zero")
    result = None
    for item in blend_spec:
        name = item["name"]
        weight = item["weight"] / total_weight
        if name not in voices_dict:
            raise ValueError(f"Voice '{name}' not found in voices file")
        contribution = voices_dict[name] * weight
        if result is None:
            result = contribution
        else:
            result = result + contribution
    return result


def load_saved_blends():
    """Load saved blends metadata from JSON file."""
    if BLENDS_JSON.is_file():
        try:
            with open(BLENDS_JSON, "r") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_saved_blends(blends):
    """Persist saved blends metadata to JSON file."""
    with open(BLENDS_JSON, "w") as f:
        json.dump(blends, f, indent=2)


def generate_audio_mp3(samples, sample_rate):
    """Convert samples array to base64-encoded MP3 audio string."""
    import soundfile as sf

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as wav_tmp:
        wav_path = wav_tmp.name
    mp3_path = wav_path.replace(".wav", ".mp3")

    try:
        sf.write(wav_path, samples, sample_rate)

        # Convert to MP3 for smaller payload
        subprocess.run(
            ["ffmpeg", "-y", "-i", wav_path, "-b:a", "128k", mp3_path],
            capture_output=True,
            timeout=30,
        )

        use_mp3 = os.path.exists(mp3_path) and os.path.getsize(mp3_path) > 0
        audio_path = mp3_path if use_mp3 else wav_path

        with open(audio_path, "rb") as f:
            audio_b64 = base64.b64encode(f.read()).decode("utf-8")

        return audio_b64, "mp3" if use_mp3 else "wav"
    finally:
        for p in [wav_path, mp3_path]:
            try:
                os.unlink(p)
            except OSError:
                pass
