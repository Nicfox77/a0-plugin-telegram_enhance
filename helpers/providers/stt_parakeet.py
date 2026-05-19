# Local ONNX Parakeet STT provider.
# Uses the onnx_asr package to run NVIDIA Parakeet models locally on CPU.
# Models are downloaded from HuggingFace on first use and cached.

from __future__ import annotations

import os
import tempfile
from typing import Any

from helpers.print_style import PrintStyle

from usr.plugins.telegram_enhance.helpers.providers import register_stt
from usr.plugins.telegram_enhance.helpers.providers.base import SttProvider


def _check_onnx_deps() -> None:
    """Verify that onnxruntime and onnx_asr are available."""
    try:
        import onnxruntime  # noqa: F401
    except ImportError:
        raise ImportError(
            "onnxruntime is required for Parakeet STT. "
            "Install with: pip install onnxruntime"
        )
    try:
        import onnx_asr  # noqa: F401
    except ImportError:
        raise ImportError(
            "onnx_asr is required for Parakeet STT. "
            "Install with: pip install onnx-asr"
        )


@register_stt("parakeet")
class ParakeetSttProvider(SttProvider):
    """Transcribe audio locally using NVIDIA Parakeet ONNX models."""

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        _check_onnx_deps()
        self.model_name: str = config.get(
            "parakeet_model", "nemo-parakeet-tdt-0.6b-v3"
        )
        self._model = None

    def _get_model(self):
        """Lazy-load the ONNX model (downloads on first use)."""
        if self._model is None:
            import onnx_asr

            PrintStyle.info(
                f"Parakeet STT: loading model '{self.model_name}' (may download on first use)..."
            )
            self._model = onnx_asr.load_model(self.model_name)
            PrintStyle.info("Parakeet STT: model loaded.")
        return self._model

    # Note: keyterms are not supported by Parakeet ONNX models. The parameter is accepted
    # for interface compatibility but has no effect on transcription.

    def transcribe(self, file_path: str, language: str | None = None, keyterms: list[str] | None = None) -> str:
        import soundfile as sf
        import numpy as np

        model = self._get_model()

        # onnx_asr expects WAV files at 16kHz mono.
        # Load audio, resample if needed, and write to a temp WAV.
        data, sr = sf.read(file_path, dtype="float32")

        # Convert stereo to mono if needed
        if data.ndim > 1:
            data = np.mean(data, axis=1)

        # Resample to 16kHz if needed
        if sr != 16000:
            try:
                import librosa

                data = librosa.resample(data, orig_sr=sr, target_sr=16000)
            except ImportError:
                try:
                    from scipy.signal import resample as scipy_resample

                    num_samples = int(len(data) * 16000 / sr)
                    data = scipy_resample(data, num_samples).astype(np.float32)
                except ImportError:
                    raise ImportError(
                        "Audio resampling requires librosa or scipy. "
                        "Install with: pip install librosa"
                    )
            sr = 16000

        # Write to temp WAV file for onnx_asr
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            sf.write(tmp.name, data, sr)
            tmp_path = tmp.name

        try:
            result = model.recognize(tmp_path)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        return result if isinstance(result, str) else str(result)
