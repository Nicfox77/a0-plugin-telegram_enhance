# OpenAI TTS provider.
# Uses the openai SDK to generate speech from text.

from __future__ import annotations

import os
from typing import Any

from usr.plugins.telegram_enhance.helpers.providers import register_tts
from usr.plugins.telegram_enhance.helpers.providers.base import TtsProvider


@register_tts("openai")
class OpenAITtsProvider(TtsProvider):
    """Generate speech via the OpenAI TTS API."""

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.api_key: str | None = (
            config.get("tts_api_key")
            or config.get("openai_api_key")
            or os.environ.get("OPENAI_API_KEY")
        )
        self.model: str = config.get("tts_openai_model", "tts-1")
        self.voice: str = config.get("tts_openai_voice", "alloy")
        if not self.api_key:
            raise ValueError(
                "OpenAI API key is required for TTS "
                "(set tts_api_key, openai_api_key, or OPENAI_API_KEY env var)"
            )

    def synthesize(self, text: str, output_path: str) -> str:
        from openai import OpenAI

        client = OpenAI(api_key=self.api_key)

        # Truncate text if too long (TTS models have limits)
        max_chars = 4096
        if len(text) > max_chars:
            text = text[:max_chars]

        response = client.audio.speech.create(
            model=self.model,
            voice=self.voice,
            input=text,
        )

        response.stream_to_file(output_path)
        return output_path
