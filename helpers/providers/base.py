"""
Base classes for STT and TTS providers.

All concrete providers inherit from SttProvider or TtsProvider and implement
the ``transcribe`` / ``synthesize`` method respectively.
"""

from __future__ import annotations

import abc
from typing import Any


class SttProvider(abc.ABC):
    """Abstract base for speech-to-text providers."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config

    @abc.abstractmethod
    def transcribe(self, file_path: str, language: str | None = None, keyterms: list[str] | None = None) -> str:
        """Transcribe *file_path* and return the text.

        Parameters
        ----------
        file_path:
            Absolute path to an audio file on disk.
        language:
            Optional BCP-47 language hint (e.g. ``"en"``).
        keyterms:
            Optional list of custom words/phrases to bias transcription.

        Returns
        -------
        str  The transcribed text.
        """

    def __repr__(self) -> str:  # pragma: no cover
        return f"<{type(self).__name__}>"


class TtsProvider(abc.ABC):
    """Abstract base for text-to-speech providers."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config

    @abc.abstractmethod
    def synthesize(self, text: str, output_path: str) -> str:
        """Synthesize *text* and write audio to *output_path*.

        Parameters
        ----------
        text:
            The text to convert to speech.
        output_path:
            Absolute path where the audio file should be written.

        Returns
        -------
        str  The *output_path* (for convenience / chaining).
        """

    def __repr__(self) -> str:  # pragma: no cover
        return f"<{type(self).__name__}>"
