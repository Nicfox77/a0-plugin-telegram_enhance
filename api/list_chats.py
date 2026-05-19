import json
import os

from helpers.api import ApiHandler, Request
from helpers import files
from agent import AgentContext


class ListChats(ApiHandler):
    """List all chats with names and Telegram link status."""

    async def process(self, input: dict, request: Request) -> dict:
        current_context_id = input.get("current_context_id", "")
        chats_dir = files.get_abs_path("usr/chats")
        if not os.path.isdir(chats_dir):
            return {"chats": []}

        chats = []
        for entry in sorted(os.listdir(chats_dir)):
            chat_json_path = os.path.join(chats_dir, entry, "chat.json")
            if not os.path.isfile(chat_json_path):
                continue
            try:
                with open(chat_json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                continue

            ctx_id = data.get("id", entry)
            name = data.get("name", "")
            created_at = data.get("created_at", "")

            # Check telegram link status from live context or chat data
            telegram_linked = False
            telegram_info = {}
            ctx = AgentContext.get(ctx_id)
            if ctx:
                bot_name = ctx.data.get("telegram_bot")
                if bot_name:
                    telegram_linked = True
                    telegram_info = {
                        "bot_name": bot_name,
                        "telegram_chat_id": ctx.data.get("telegram_chat_id"),
                        "telegram_user_id": ctx.data.get("telegram_user_id"),
                        "telegram_username": ctx.data.get("telegram_username", ""),
                    }

            chat_entry = {
                "id": ctx_id,
                "name": name or ctx_id,
                "created_at": created_at,
                "telegram_linked": telegram_linked,
                "is_current": ctx_id == current_context_id,
            }
            if telegram_info:
                chat_entry["telegram_info"] = telegram_info

            chats.append(chat_entry)

        return {"chats": chats}
