import re
import numpy as np
from helpers.api import ApiHandler, Request
from helpers.print_style import PrintStyle

from usr.plugins.telegram_enhance.api.voice_lab_shared import (
    _lock,
    VOICES_PATH,
    load_voices,
    compute_blend,
    load_saved_blends,
    save_saved_blends,
)


class VoiceLabSave(ApiHandler):
    """Save a voice blend as a new named voice in voices_custom.npz."""

    async def process(self, input: dict, request: Request) -> dict:
        name = input.get("name", "").strip()
        blend_spec = input.get("voices", [])

        if not name:
            return {"error": "Blend name is required"}
        if not blend_spec:
            return {"error": "No voices specified for blend"}

        clean_name = re.sub(r"[^a-zA-Z0-9_-]", "_", name)
        if not clean_name:
            return {"error": "Invalid blend name"}

        try:
            with _lock:
                voices_dict = load_voices()
                blend_array = compute_blend(voices_dict, blend_spec)
                voices_dict[clean_name] = blend_array
                np.savez(str(VOICES_PATH), **voices_dict)

                saved_blends = load_saved_blends()
                saved_blends = [b for b in saved_blends if b["name"] != clean_name]
                saved_blends.append({
                    "name": clean_name,
                    "voices": blend_spec,
                    "display_name": name,
                })
                save_saved_blends(saved_blends)

            return {
                "success": True,
                "name": clean_name,
                "message": f"Blend '{clean_name}' saved with {len(blend_spec)} voices",
            }
        except Exception as e:
            PrintStyle.error(f"Voice Lab save error: {e}")
            return {"error": str(e)}
