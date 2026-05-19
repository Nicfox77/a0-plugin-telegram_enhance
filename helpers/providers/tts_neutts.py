from __future__ import annotations

from typing import Any

from helpers.print_style import PrintStyle

from usr.plugins.telegram_enhance.helpers.providers import register_tts
from usr.plugins.telegram_enhance.helpers.providers.base import TtsProvider


@register_tts("neutts")
class NeuTtsProvider(TtsProvider):
    """Generate speech via NeuTTS (Neuphonic)."""

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.backbone_repo = config.get("neutts_model", "neuphonic/neutts-nano")
        self.backbone_device = config.get("neutts_device", "cpu")
        self.codec_repo = config.get("neutts_codec_repo", "neuphonic/neucodec")
        self.codec_device = config.get("neutts_codec_device", "cpu")
        self.language = config.get("neutts_language") or None
        self.ref_audio = config.get("neutts_ref_audio") or None
        self.ref_text = config.get("neutts_ref_text") or None
        self._tts = None
        self._ref_codes = None
        self._available = None

    def _check_available(self) -> bool:
        if self._available is None:
            try:
                from neutts import NeuTTS  # noqa: F401

                self._available = True
            except ImportError:
                self._available = False
                PrintStyle.warning(
                    "NeuTTS: neutts package not installed. "
                    "Install with: pip install neutts"
                )
        return self._available

    def _get_tts(self):
        if self._tts is None:
            if not self._check_available():
                raise ImportError(
                    "neutts package not installed. Install with: pip install neutts"
                )
            from neutts import NeuTTS

            kwargs: dict[str, Any] = {
                "backbone_repo": self.backbone_repo,
                "backbone_device": self.backbone_device,
                "codec_repo": self.codec_repo,
                "codec_device": self.codec_device,
            }
            if self.language:
                kwargs["language"] = self.language

            PrintStyle.info(f"NeuTTS: loading model {self.backbone_repo}...")
            self._tts = NeuTTS(**kwargs)

            # Encode reference audio if provided
            if self.ref_audio:
                PrintStyle.info(f"NeuTTS: encoding reference audio from {self.ref_audio}")
                self._ref_codes = self._tts.encode_reference(self.ref_audio)
            else:
                import numpy as np

                self._ref_codes = np.array([], dtype=np.int64)

            PrintStyle.info("NeuTTS: model loaded.")
        return self._tts

    def synthesize(self, text: str, output_path: str) -> str:
        import numpy as np
        import soundfile as sf

        tts = self._get_tts()

        # Truncate text if too long
        max_chars = 5000
        if len(text) > max_chars:
            text = text[:max_chars]

        ref_text = self.ref_text or "a"
        audio = tts.infer(text, self._ref_codes, ref_text)

        # audio is a numpy array at 24kHz sample rate
        sample_rate = tts.sample_rate  # 24000

        # Ensure float32 for soundfile
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)

        sf.write(output_path, audio, sample_rate)
        PrintStyle.info(f"NeuTTS: audio saved to {output_path} ({len(audio)/sample_rate:.1f}s)")
        return output_path
