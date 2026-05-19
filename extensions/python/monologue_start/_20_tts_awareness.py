# TTS Awareness Prompt Injection - monologue_start extension
#
# When TTS voice responses are enabled for the current Telegram chat, this
# extension injects a system-level awareness prompt into the agent's context
# so the LLM knows to respond in a natural, audio-friendly conversational
# style (no markdown, bullet points, emoji, code blocks, etc.).

from helpers.extension import Extension
from helpers import plugins
from agent import LoopData

try:
    from plugins._telegram_integration.helpers.constants import (
        CTX_TG_BOT,
        CTX_TG_CHAT_ID,
    )
    _TG_AVAILABLE = True
except ImportError:
    _TG_AVAILABLE = False


_TTS_AWARENESS_PROMPT = (
    "TTS voice responses are enabled for this conversation. "
    "Your response will be converted to audio and read aloud. "
    "Follow these rules: respond in a natural conversational tone "
    "as if speaking to someone. Do not use emojis, bullet points, "
    "numbered lists, tables, markdown formatting, code blocks, "
    "or special characters. Keep responses concise and "
    "well-structured for audio. Use plain sentences and short paragraphs."
)


class TtsAwareness(Extension):

    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        if not self.agent or self.agent.number != 0:
            return

        if not _TG_AVAILABLE:
            return

        context = self.agent.context
        if not context.data.get(CTX_TG_BOT):
            return

        # Clear the TTS text accumulator for this chat (new user message = new turn)
        chat_id = context.data.get(CTX_TG_CHAT_ID)
        if chat_id:
            try:
                from usr.plugins.telegram_enhance.helpers.tts_text_accumulator import clear_accumulated_text
                clear_accumulated_text(int(chat_id))
            except Exception:
                pass

        # Determine whether TTS is active for this chat
        config = plugins.get_plugin_config(
            "telegram_enhance", agent=self.agent
        ) or {}

        # Per-chat override in context.data takes priority
        per_chat_tts = context.data.get("_tg_tts_enabled")
        if per_chat_tts is None:
            # Fallback to persistent storage
            chat_id = context.data.get(CTX_TG_CHAT_ID)
            if chat_id is not None:
                try:
                    from usr.plugins.telegram_enhance.helpers.tts_state import (
                        get_tts_enabled,
                    )
                    per_chat_tts = get_tts_enabled(chat_id)
                except Exception:
                    pass
            if per_chat_tts is None:
                # Final fallback: global config
                per_chat_tts = config.get("tts_enabled", False)

        if not per_chat_tts:
            return

        # Inject the awareness prompt via extras_persistent so it appears in
        # every LLM call for this monologue cycle.
        loop_data.extras_persistent["tts_awareness"] = _TTS_AWARENESS_PROMPT
