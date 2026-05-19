"""Persistent storage for TTS message IDs.

context.data resets between conversation turns, so we need
to persist the IDs to a JSON file keyed by Telegram chat ID.
"""
import json
import os
from pathlib import Path
from helpers.print_style import PrintStyle

_STATE_FILE = Path(__file__).resolve().parent.parent / "tts_msg_ids.json"


def _load() -> dict:
    """Load the full state dict from disk."""
    if _STATE_FILE.exists():
        try:
            return json.loads(_STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save(state: dict):
    """Save the full state dict to disk."""
    _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def get_last_tts_msg_ids(chat_id: int) -> list[int] | None:
    """Get the last TTS message IDs for a chat."""
    state = _load()
    key = str(chat_id)
    ids = state.get(key)
    if ids and isinstance(ids, list):
        return ids
    return None


def set_last_tts_msg_ids(chat_id: int, msg_ids: list[int]):
    """Store TTS message IDs for a chat."""
    state = _load()
    key = str(chat_id)
    if msg_ids:
        state[key] = msg_ids
    elif key in state:
        del state[key]
    _save(state)
    PrintStyle(font_color="cyan", padding=True).print(
        f"TTS MSG IDS: saved {msg_ids} for chat {chat_id}"
    )


def clear_last_tts_msg_ids(chat_id: int):
    """Remove stored TTS message IDs for a chat."""
    state = _load()
    key = str(chat_id)
    if key in state:
        del state[key]
        _save(state)
