import json
import os

from helpers.api import ApiHandler, Request
from helpers import files, plugins as plugin_helpers
from agent import AgentContext


class AttachChat(ApiHandler):
    """Directly attach a web chat context to a Telegram conversation.

    Called from the web UI to link a context to an existing Telegram session.
    Input: { context_id, bot_name, user_id, chat_id, username }
    """

    async def process(self, input: dict, request: Request) -> dict:
        context_id = input.get("context_id", "")
        bot_name = input.get("bot_name", "")
        user_id = input.get("user_id")
        chat_id = input.get("chat_id")
        username = input.get("username", "")

        if not context_id:
            return {"success": False, "error": "No context_id provided"}
        if not bot_name:
            return {"success": False, "error": "No bot_name provided"}
        if user_id is None or chat_id is None:
            return {"success": False, "error": "user_id and chat_id are required"}

        # Look up the target context
        ctx = AgentContext.get(context_id)
        if not ctx:
            return {"success": False, "error": f"Context {context_id} not found"}

        # Load telegram state
        from plugins._telegram_integration.helpers.handler import _load_state, _save_state, _map_key
        from plugins._telegram_integration.helpers.constants import (
            CTX_TG_BOT, CTX_TG_BOT_CFG, CTX_TG_CHAT_ID, CTX_TG_USER_ID, CTX_TG_USERNAME,
        )

        state = _load_state()
        key = _map_key(bot_name, user_id, chat_id)

        # If this telegram session already points to a different context, clear it
        old_ctx_id = state.get("chats", {}).get(key)
        if old_ctx_id and old_ctx_id != context_id:
            old_ctx = AgentContext.get(old_ctx_id)
            if old_ctx:
                old_ctx.data.pop(CTX_TG_BOT, None)
                old_ctx.data.pop(CTX_TG_BOT_CFG, None)
                old_ctx.data.pop(CTX_TG_CHAT_ID, None)
                old_ctx.data.pop(CTX_TG_USER_ID, None)
                old_ctx.data.pop(CTX_TG_USERNAME, None)

        # If this context is already linked to a different telegram session, clear that mapping
        existing_bot = ctx.data.get(CTX_TG_BOT)
        if existing_bot:
            existing_chat_id = ctx.data.get(CTX_TG_CHAT_ID)
            existing_user_id = ctx.data.get(CTX_TG_USER_ID)
            if existing_chat_id is not None and existing_user_id is not None:
                old_key = _map_key(existing_bot, existing_user_id, existing_chat_id)
                chats = state.get("chats", {})
                if chats.get(old_key) == context_id:
                    chats.pop(old_key, None)

        # Load bot config from telegram integration plugin
        tg_config = plugin_helpers.get_plugin_config("_telegram_integration") or {}
        bots_cfg = tg_config.get("bots") or []
        bot_cfg = {}
        for b in bots_cfg:
            if b.get("name") == bot_name:
                bot_cfg = b
                break

        # Set telegram data on the context
        ctx.data[CTX_TG_BOT] = bot_name
        ctx.data[CTX_TG_BOT_CFG] = bot_cfg
        ctx.data[CTX_TG_CHAT_ID] = chat_id
        ctx.data[CTX_TG_USER_ID] = user_id
        ctx.data[CTX_TG_USERNAME] = username or ""

        # Update state mapping
        state.setdefault("chats", {})[key] = context_id
        _save_state(state)

        return {
            "success": True,
            "context_id": context_id,
            "bot_name": bot_name,
            "chat_id": chat_id,
        }
