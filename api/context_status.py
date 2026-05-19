from helpers.api import ApiHandler, Request
from agent import AgentContext


class ContextStatus(ApiHandler):
    """Check if a context is linked to Telegram and return the status."""

    async def process(self, input: dict, request: Request) -> dict:
        context_id = input.get("context_id", "")
        if not context_id:
            return {"linked": False, "error": "No context_id provided"}

        ctx = AgentContext.get(context_id)
        if not ctx:
            return {"linked": False, "error": "Context not found"}

        bot_name = ctx.data.get("telegram_bot")
        if bot_name:
            return {
                "linked": True,
                "bot_name": bot_name,
                "telegram_chat_id": ctx.data.get("telegram_chat_id"),
                "telegram_username": ctx.data.get("telegram_username", ""),
            }

        return {"linked": False}
