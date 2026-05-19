import numpy as np
from helpers.api import ApiHandler, Request
from helpers.print_style import PrintStyle

from usr.plugins.telegram_enhance.api.voice_lab_shared import (
    VOICES_PATH,
    load_saved_blends,
)


class VoiceLabListVoices(ApiHandler):
    """Return all available voice names from voices_custom.npz."""

    async def process(self, input: dict, request: Request) -> dict:
        voices = np.load(str(VOICES_PATH))
        voice_names = sorted(voices.files)
        saved_blends = load_saved_blends()
        return {
            "voices": voice_names,
            "saved_blends": saved_blends,
        }
