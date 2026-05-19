"""
X.ai Grok STT provider.

Uses the X.ai /v1/stt REST endpoint for transcription.
The endpoint accepts multipart/form-data with audio files.
"""

from __future__ import annotations

import os
from typing import Any

import requests

from usr.plugins.telegram_enhance.helpers.providers import register_stt
from usr.plugins.telegram_enhance.helpers.providers.base import SttProvider

XAI_STT_URL = "https://api.x.ai/v1/stt"


@register_stt("xai")
class XAISttProvider(SttProvider):
    """Transcribe audio via the X.ai Grok STT API."""

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.api_key: str | None = config.get("xai_api_key") or os.environ.get(
            "XAI_API_KEY"
        )
        if not self.api_key:
            raise ValueError(
                "X.ai API key is required (set xai_api_key in config or XAI_API_KEY env var)"
            )

    def transcribe(self, file_path: str, language: str | None = None, keyterms: list[str] | None = None) -> str:
        headers = {"Authorization": f"Bearer {self.api_key}"}

        with open(file_path, "rb") as audio_file:
            # Determine content type from extension
            ext = os.path.splitext(file_path)[1].lower()
            content_type = self._content_type(ext)

            form_fields: list[tuple[str, Any]] = []

            # Enable text formatting when language is provided
            if language:
                form_fields.append(("format", "true"))
                form_fields.append(("language", language))

            if keyterms:
                for term in keyterms:
                    form_fields.append(('keyterm', term))

            # File must be the last field in the multipart form
            form_fields.append(
                ("file", (os.path.basename(file_path), audio_file, content_type))
            )

            response = requests.post(
                XAI_STT_URL,
                headers=headers,
                files=form_fields,
                timeout=120,
            )

        response.raise_for_status()
        result = response.json()
        return result.get("text", "")

    @staticmethod
    def _content_type(ext: str) -> str:
        """Map file extension to MIME type."""
        return {
            ".mp3": "audio/mpeg",
            ".wav": "audio/wav",
            ".ogg": "audio/ogg",
            ".opus": "audio/opus",
            ".flac": "audio/flac",
            ".m4a": "audio/mp4",
            ".aac": "audio/aac",
            ".webm": "audio/webm",
            ".mp4": "audio/mp4",
        }.get(ext, "application/octet-stream")
