import os
from typing import Any

from helpers.print_style import PrintStyle

from usr.plugins.telegram_enhance.helpers.providers import register_tts
from usr.plugins.telegram_enhance.helpers.providers.base import TtsProvider


@register_tts("kokoro")
class KokoroTtsProvider(TtsProvider):
    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        models_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__)
            ))),
            'models'
        )
        self.onnx_path = config.get('kokoro_model_path') or os.path.join(models_dir, 'kokoro.onnx')
        self.voices_path = config.get('kokoro_voices_path') or os.path.join(models_dir, 'voices_custom.npz')
        self.voice = config.get('kokoro_voice', 'af_sky')
        self.speed = float(config.get('kokoro_speed', 1.0))
        self.lang = config.get('kokoro_lang', 'en-us')
        self._session = None
        self._kokoro = None

    def _get_kokoro(self):
        if self._kokoro is None:
            try:
                from kokoro_onnx import Kokoro
            except ImportError:
                raise ImportError(
                    "kokoro-onnx is required for Kokoro TTS. "
                    "Install with: pip install kokoro-onnx onnxruntime"
                )
            PrintStyle.info(f"Kokoro TTS: loading model from {self.onnx_path}...")
            self._kokoro = Kokoro(self.onnx_path, self.voices_path)
            PrintStyle.info("Kokoro TTS: model loaded.")
        return self._kokoro

    def synthesize(self, text: str, output_path: str) -> str:
        import soundfile as sf

        kokoro = self._get_kokoro()

        # Truncate text if too long
        max_chars = 5000
        if len(text) > max_chars:
            text = text[:max_chars]

        samples, sample_rate = kokoro.create(
            text, voice=self.voice, speed=self.speed, lang=self.lang
        )
        sf.write(output_path, samples, sample_rate)
        return output_path
