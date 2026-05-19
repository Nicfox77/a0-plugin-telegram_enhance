"""
OpenAI Whisper STT provider.

Uses the ``openai`` SDK to call the Whisper transcription API.
"""

from __future__ import annotations

import os
from typing import Any

from helpers.print_style import PrintStyle

from usr.plugins.telegram_enhance.helpers.providers import register_stt
from usr.plugins.telegram_enhance.helpers.providers.base import SttProvider


@register_stt("openai")
class OpenAISttProvider(SttProvider):
    """Transcribe audio via the OpenAI Whisper API."""

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.api_key: str | None = config.get("openai_api_key") or os.environ.get(
            "OPENAI_API_KEY"
        )
        self.model: str = config.get("openai_model", "whisper-1")
        if not self.api_key:
            raise ValueError(
                "OpenAI API key is required (set openai_api_key in config or OPENAI_API_KEY env var)"
            )

    def transcribe(self, file_path: str, language: str | None = None, keyterms: list[str] | None = None) -> str:
        from openai import OpenAI

        client = OpenAI(api_key=self.api_key)

        with open(file_path, "rb") as audio_file:
            kwargs: dict[str, Any] = {
                "model": self.model,
                "file": audio_file,
                "response_format": "text",
            }
            if language:
                kwargs["language"] = language
            if keyterms:
                kwargs["prompt"] = " ".join(keyterms)
            result = client.audio.transcriptions.create(**kwargs)

        return result if isinstance(result, str) else result.text
