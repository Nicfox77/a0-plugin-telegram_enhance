# STT/TTS provider registry
from usr.plugins.telegram_enhance.helpers.providers.base import (
    SttProvider,
    TtsProvider,
)

STT_PROVIDERS = {}
TTS_PROVIDERS = {}


def register_stt(name: str):
    def decorator(cls):
        STT_PROVIDERS[name] = cls
        return cls
    return decorator


def register_tts(name: str):
    def decorator(cls):
        TTS_PROVIDERS[name] = cls
        return cls
    return decorator


def get_stt_provider(name: str, config: dict) -> SttProvider:
    cls = STT_PROVIDERS.get(name)
    if cls is None:
        raise ValueError(f"Unknown STT provider: {name}")
    return cls(config)


def get_tts_provider(name: str, config: dict) -> TtsProvider:
    cls = TTS_PROVIDERS.get(name)
    if cls is None:
        raise ValueError(f"Unknown TTS provider: {name}")
    return cls(config)


# Import providers to trigger registration
import usr.plugins.telegram_enhance.helpers.providers.stt_openai  # noqa: F401
import usr.plugins.telegram_enhance.helpers.providers.stt_xai  # noqa: F401
import usr.plugins.telegram_enhance.helpers.providers.stt_parakeet  # noqa: F401
import usr.plugins.telegram_enhance.helpers.providers.tts_openai  # noqa: F401
import usr.plugins.telegram_enhance.helpers.providers.tts_edge  # noqa: F401
import usr.plugins.telegram_enhance.helpers.providers.tts_kokoro  # noqa: F401
import usr.plugins.telegram_enhance.helpers.providers.tts_neutts  # noqa: F401
