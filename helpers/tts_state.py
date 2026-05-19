# TTS State Persistence
#
# Manages per-chat TTS state (enabled flag and voice selection) that survives
# restarts.  State is stored in a simple JSON file keyed by Telegram chat ID.

import json
import os

STATE_FILE = os.path.join(os.path.dirname(__file__), '..', 'tts_state.json')


def _load_state() -> dict:
    path = os.path.normpath(STATE_FILE)
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}


def _save_state(state: dict):
    path = os.path.normpath(STATE_FILE)
    with open(path, 'w') as f:
        json.dump(state, f, indent=2)


def get_tts_enabled(chat_id) -> bool | None:
    """Return per-chat TTS enabled flag, or None if not set."""
    state = _load_state()
    key = str(chat_id)
    return state.get(key, {}).get('tts_enabled')


def set_tts_enabled(chat_id, enabled: bool):
    """Persist the per-chat TTS enabled flag."""
    state = _load_state()
    key = str(chat_id)
    state.setdefault(key, {})['tts_enabled'] = enabled
    _save_state(state)


def get_tts_voice(chat_id) -> str | None:
    """Return per-chat TTS voice name, or None if not set."""
    state = _load_state()
    key = str(chat_id)
    return state.get(key, {}).get('tts_voice')


def set_tts_voice(chat_id, voice: str):
    """Persist the per-chat TTS voice selection."""
    state = _load_state()
    key = str(chat_id)
    state.setdefault(key, {})['tts_voice'] = voice
    _save_state(state)
