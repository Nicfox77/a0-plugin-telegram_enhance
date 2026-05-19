import numpy as np
from helpers.api import ApiHandler, Request
from helpers.print_style import PrintStyle

from usr.plugins.telegram_enhance.api.voice_lab_shared import (
    _lock,
    VOICES_PATH,
    load_voices,
    load_saved_blends,
    save_saved_blends,
)


class VoiceLabDeleteBlend(ApiHandler):
    """Delete a saved blend from voices_custom.npz and saved_blends.json."""

    async def process(self, input: dict, request: Request) -> dict:
        name = input.get("name", "").strip()
        if not name:
            return {"error": "Blend name is required"}

        try:
            with _lock:
                voices_dict = load_voices()
                if name not in voices_dict:
                    return {"error": f"Blend '{name}' not found"}

                saved_blends = load_saved_blends()
                blend_names = [b["name"] for b in saved_blends]
                if name not in blend_names:
                    return {"error": f"'{name}' is a base voice and cannot be deleted"}

                del voices_dict[name]
                np.savez(str(VOICES_PATH), **voices_dict)
                saved_blends = [b for b in saved_blends if b["name"] != name]
                save_saved_blends(saved_blends)

            return {
                "success": True,
                "name": name,
                "message": f"Blend '{name}' deleted",
            }
        except Exception as e:
            PrintStyle.error(f"Voice Lab delete error: {e}")
            return {"error": str(e)}
