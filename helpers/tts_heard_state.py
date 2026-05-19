"""Persistent storage for TTS 'heard' state.

Tracks which TTS audio messages have been acknowledged (reacted to) by users.
This allows the consolidation logic to know whether the previous audio clip
has been 'heard' before deciding whether to consolidate.
"""
import json
import os
from pathlib import Path
from helpers.print_style import PrintStyle

_STATE_FILE = Path(__file__).resolve().parent.parent / "tts_heard_state.json"


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


def mark_as_heard(chat_id: int, message_id: int):
    """Mark a TTS audio message as 'heard' for a chat."""
    state = _load()
    key = str(chat_id)
    if key not in state:
        state[key] = []
    
    # Store as list of (message_id, timestamp) tuples for tracking
    heard_list = state[key]
    
    # Check if already marked
    for item in heard_list:
        if item.get("msg_id") == message_id:
            return  # Already marked
    
    # Add new entry
    heard_list.append({
        "msg_id": message_id,
        "timestamp": int(os.times().elapsed * 1000) if hasattr(os, "times") else 0
    })
    
    state[key] = heard_list
    _save(state)
    PrintStyle(font_color="cyan", padding=True).print(
        f"TTS HEARD: marked msg {message_id} as heard in chat {chat_id}"
    )


def is_heard(chat_id: int, message_id: int) -> bool:
    """Check if a TTS audio message has been marked as 'heard'."""
    state = _load()
    key = str(chat_id)
    if key not in state:
        return False
    
    heard_list = state[key]
    for item in heard_list:
        if item.get("msg_id") == message_id:
            return True
    return False


def cleanup_old_entries(chat_id: int, keep_recent: int = 10):
    """Remove old heard entries for a chat, keeping only the most recent ones.
    
    Args:
        chat_id: The Telegram chat ID
        keep_recent: Number of recent entries to keep (default: 10)
    """
    state = _load()
    key = str(chat_id)
    if key not in state:
        return
    
    heard_list = state[key]
    if len(heard_list) <= keep_recent:
        return
    
    # Keep only the last keep_recent entries (they are appended in order)
    state[key] = heard_list[-keep_recent:]
    _save(state)
    PrintStyle(font_color="cyan", padding=True).print(
        f"TTS HEARD: cleaned up {len(heard_list) - keep_recent} old entries for chat {chat_id}, kept {keep_recent}"
    )


def get_heard_message_ids(chat_id: int) -> list[int]:
    """Get all heard message IDs for a chat."""
    state = _load()
    key = str(chat_id)
    if key not in state:
        return []
    return [item.get("msg_id") for item in state[key] if "msg_id" in item]


def clear_heard_state(chat_id: int):
    """Clear all heard state for a chat."""
    state = _load()
    key = str(chat_id)
    if key in state:
        del state[key]
        _save(state)
