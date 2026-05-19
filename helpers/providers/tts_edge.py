# Edge TTS provider.
# Uses the edge_tts package to generate speech from text.
# Free, no API key required.

from __future__ import annotations

import asyncio
from typing import Any

from usr.plugins.telegram_enhance.helpers.providers import register_tts
from usr.plugins.telegram_enhance.helpers.providers.base import TtsProvider


@register_tts("edge_tts")
class EdgeTtsProvider(TtsProvider):
    """Generate speech via Microsoft Edge TTS (free, no API key)."""

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.voice: str = config.get("tts_edge_voice", "en-US-AvaNeural")

    def synthesize(self, text: str, output_path: str) -> str:
        import edge_tts  # noqa: F401

        # Truncate text if too long
        max_chars = 5000
        if len(text) > max_chars:
            text = text[:max_chars]

        # edge_tts is async, so we need to run it in an event loop
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # We're inside an async context already - run in a separate thread
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(
                    asyncio.run, self._synthesize_async(text, output_path)
                )
                future.result()
        else:
            asyncio.run(self._synthesize_async(text, output_path))

        return output_path

    async def _synthesize_async(self, text: str, output_path: str) -> None:
        import edge_tts

        communicate = edge_tts.Communicate(text, self.voice)
        await communicate.save(output_path)
