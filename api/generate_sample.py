from helpers.api import ApiHandler, Request
from helpers.print_style import PrintStyle

from usr.plugins.telegram_enhance.api.voice_lab_shared import (
    _lock,
    load_voices,
    compute_blend,
    get_kokoro,
    generate_audio_mp3,
)


class VoiceLabGenerate(ApiHandler):
    """Generate an audio sample from a voice blend and return as base64 MP3."""

    async def process(self, input: dict, request: Request) -> dict:
        blend_spec = input.get("voices", [])
        text = input.get("text", "Hello, this is a test of my custom voice blend.")
        speed = float(input.get("speed", 1.1))

        if not blend_spec:
            return {"error": "No voices specified for blend"}
        if not text or not text.strip():
            return {"error": "No text provided"}

        speed = max(0.5, min(2.0, speed))
        if len(text) > 1000:
            text = text[:1000]

        with _lock:
            try:
                voices_dict = load_voices()
                blend_array = compute_blend(voices_dict, blend_spec)
                kokoro = get_kokoro()
                samples, sample_rate = kokoro.create(
                    text, voice=blend_array, speed=speed, lang="en-us"
                )
            except Exception as e:
                PrintStyle.error(f"Voice Lab generate error: {e}")
                return {"error": str(e)}

        try:
            audio_b64, fmt = generate_audio_mp3(samples, sample_rate)
            return {
                "audio": audio_b64,
                "format": fmt,
                "sample_rate": sample_rate,
                "duration": round(len(samples) / sample_rate, 2),
            }
        except Exception as e:
            PrintStyle.error(f"Voice Lab audio encoding error: {e}")
            return {"error": str(e)}
