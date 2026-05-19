"""Persistent storage for TTS text accumulation.

context.data resets between process_chain_end calls within a turn,
so we persist accumulated TTS text to a JSON file keyed by Telegram chat ID.
This allows _40_tts_response to build up the full response text across
multiple chain iterations (when break_loop is false).

The accumulator is cleared at monologue_start (when a new user message
arrives), so each agent turn starts fresh.
"""

import json
from pathlib import Path
from helpers.print_style import PrintStyle

_STATE_FILE = Path(__file__).resolve().parent.parent / "tts_text_accumulator.json"


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


def get_accumulated_text(chat_id: int) -> str | None:
    """Get the accumulated TTS text for a chat, or None if not set."""
    state = _load()
    key = str(chat_id)
    return state.get(key)


def set_accumulated_text(chat_id: int, text: str):
    """Store accumulated TTS text for a chat."""
    state = _load()
    key = str(chat_id)
    if text:
        state[key] = text
    elif key in state:
        del state[key]
    _save(state)
    PrintStyle(font_color="cyan", padding=True).print(
        f"TTS TEXT ACCUMULATOR: saved {len(text)} chars for chat {chat_id}"
    )


def append_accumulated_text(chat_id: int, new_text: str) -> str:
    """Append new text to existing accumulated text for a chat.

    If there is existing text, the chunks are joined with '. '
    for natural TTS reading. Returns the full accumulated text.
    """
    existing = get_accumulated_text(chat_id) or ""
    if existing:
        # Ensure existing doesn't already end with sentence-ending punctuation
        combined = existing.rstrip() + ". " + new_text.lstrip()
    else:
        combined = new_text
    set_accumulated_text(chat_id, combined)
    return combined


def clear_accumulated_text(chat_id: int):
    """Remove stored accumulated TTS text for a chat."""
    state = _load()
    key = str(chat_id)
    if key in state:
        del state[key]
        _save(state)
        PrintStyle(font_color="cyan", padding=True).print(
            f"TTS TEXT ACCUMULATOR: cleared for chat {chat_id}"
        )
