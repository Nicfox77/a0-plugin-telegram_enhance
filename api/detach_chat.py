from helpers.api import ApiHandler, Request
from agent import AgentContext


class DetachChat(ApiHandler):
    """Directly detach a web chat context from Telegram.

    Called from the web UI to remove the Telegram link from a context.
    Input: { context_id }
    """

    async def process(self, input: dict, request: Request) -> dict:
        context_id = input.get("context_id", "")
        if not context_id:
            return {"success": False, "error": "No context_id provided"}

        ctx = AgentContext.get(context_id)
        if not ctx:
            return {"success": False, "error": f"Context {context_id} not found"}

        from plugins._telegram_integration.helpers.handler import _load_state, _save_state, _map_key
        from plugins._telegram_integration.helpers.constants import (
            CTX_TG_BOT, CTX_TG_BOT_CFG, CTX_TG_CHAT_ID, CTX_TG_USER_ID, CTX_TG_USERNAME,
        )

        # Get current telegram info before clearing
        bot_name = ctx.data.get(CTX_TG_BOT)
        chat_id = ctx.data.get(CTX_TG_CHAT_ID)
        user_id = ctx.data.get(CTX_TG_USER_ID)

        if not bot_name:
            return {"success": False, "error": "Context is not linked to Telegram"}

        # Remove state mapping
        state = _load_state()
        if chat_id is not None and user_id is not None:
            key = _map_key(bot_name, user_id, chat_id)
            state.get("chats", {}).pop(key, None)
            _save_state(state)

        # Clear telegram data from context
        ctx.data.pop(CTX_TG_BOT, None)
        ctx.data.pop(CTX_TG_BOT_CFG, None)
        ctx.data.pop(CTX_TG_CHAT_ID, None)
        ctx.data.pop(CTX_TG_USER_ID, None)
        ctx.data.pop(CTX_TG_USERNAME, None)

        return {
            "success": True,
            "context_id": context_id,
        }
