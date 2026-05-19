# Telegram TTS Audio Track - process_chain_end extension
#
# After the telegram reply extension (_55) sends attachments, this extension
# captures the sent message IDs for TTS audio files so they can be deleted
# on the next TTS cycle (by _40_tts_response.py).
#
# Also auto-reacts to TTS messages with headphones emoji when audio_consolidation
# is enabled, so the system can track which clips have been "heard".
#
# Priority 56 runs after the built-in telegram reply at priority 55.

import asyncio
from contextlib import asynccontextmanager
from helpers.extension import Extension
from helpers.print_style import PrintStyle
import json, time
from helpers import plugins
from agent import AgentContext, LoopData

try:
    from plugins._telegram_integration.helpers.constants import (
        CTX_TG_BOT,
        CTX_TG_ATTACHMENTS,
        CTX_TG_CHAT_ID,
    )
    _TG_AVAILABLE = True
except ImportError:
    _TG_AVAILABLE = False
    CTX_TG_CHAT_ID = "telegram_chat_id"

# Context data keys
CTX_TTS_PENDING_COUNT = "_tg_tts_pending_attachment_count"
CTX_TTS_LAST_MSG_IDS = "_tg_last_tts_message_ids"

# Reaction emoji for TTS audio messages
# Note: Telegram only allows specific emojis as reactions. 👀 = "seen/listening"
_TTS_REACTION_EMOJI = "👀"


@asynccontextmanager
async def _temp_bot(token: str):
    """Create a temporary Bot for cross-event-loop safety."""
    from aiogram import Bot
    bot = Bot(token=token)
    try:
        yield bot
    finally:
        try:
            await bot.session.close()
        except Exception:
            pass


async def _set_tts_reaction(bot_name: str, chat_id: int, message_ids: list[int]):
    """Add headphones reaction to TTS audio messages via direct HTTP API call.
    
    Bypasses aiogram's set_message_reaction() because it uses asyncio.timeout()
    internally which requires a Task context that extensions don't run in.
    """
    import time as _time
    import json
    try:
        from plugins._telegram_integration.helpers.bot_manager import get_bot
        import aiohttp
    except ImportError as e:
        with open("/tmp/tts_56_trace.log", "a") as _f:
            _f.write(f"{_time.strftime('%H:%M:%S')} _set_tts_reaction IMPORT ERROR: {e}\n")
        return
    
    instance = get_bot(bot_name)
    if not instance:
        with open("/tmp/tts_56_trace.log", "a") as _f:
            _f.write(f"{_time.strftime('%H:%M:%S')} _set_tts_reaction: NO BOT INSTANCE\n")
        return
    
    token = instance.bot.token
    url = f"https://api.telegram.org/bot{token}/setMessageReaction"
    
    for msg_id in message_ids:
        try:
            payload = {
                "chat_id": chat_id,
                "message_id": msg_id,
                "reaction": json.dumps([{"type": "emoji", "emoji": _TTS_REACTION_EMOJI}])
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=payload) as resp:
                    result = await resp.json()
            with open("/tmp/tts_56_trace.log", "a") as _f:
                _f.write(f"{_time.strftime('%H:%M:%S')} _set_tts_reaction HTTP: msg={msg_id} status={resp.status} result={result}\n")
            if result.get("ok"):
                PrintStyle(font_color="cyan", padding=True).print(
                    f"TTS REACT: added 🎧 to msg {msg_id} in chat {chat_id}"
                )
            else:
                PrintStyle.debug(f"TTS REACT: Telegram API error for msg {msg_id}: {result}")
        except Exception as e:
            with open("/tmp/tts_56_trace.log", "a") as _f:
                _f.write(f"{_time.strftime('%H:%M:%S')} _set_tts_reaction HTTP FAILED for msg {msg_id}: {type(e).__name__}: {e}\n")
            PrintStyle.debug(f"TTS REACT: failed for msg {msg_id}: {e}")


class TtsAudioTrack(Extension):

    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        if not self.agent or self.agent.number != 0:
            return

        if not _TG_AVAILABLE:
            return

        context = self.agent.context
        if not context.data.get(CTX_TG_BOT):
            return

        # Check if TTS was active this cycle (set by _40_tts_response.py)
        pending_count = context.data.get(CTX_TTS_PENDING_COUNT, 0)
        with open("/tmp/tts_56_trace.log", "a") as _f:
            _f.write(f"{time.strftime('%H:%M:%S')} _56 fired: pending={pending_count} keys={list(context.data.keys())}\n")
        PrintStyle(font_color="cyan", padding=True).print(
            f"TTS DEBUG _56: pending_count={pending_count}, "
            f"ctx keys={list(context.data.keys())[:10]}"
        )
        if not pending_count:
            return

        # Read the attachment msg_ids that _55_telegram_reply stored
        sent_ids = context.data.pop("_tg_sent_attachment_msg_ids", None)
        with open("/tmp/tts_56_trace.log", "a") as _f:
            _f.write(f"{time.strftime('%H:%M:%S')} _56 sent_ids={sent_ids}\n")
        PrintStyle(font_color="cyan", padding=True).print(
            f"TTS DEBUG _56: sent_ids={sent_ids}, pending={pending_count}"
        )
        if not sent_ids:
            PrintStyle(font_color="yellow", padding=True).print(
                "TTS DEBUG _56: no sent_attachment_msg_ids found!"
            )
            context.data.pop(CTX_TTS_PENDING_COUNT, None)
            return

        # The TTS audio attachments are always at the END of the attachments list.
        # Take the last N ids where N = pending_count.
        tts_ids = sent_ids[-pending_count:] if pending_count <= len(sent_ids) else sent_ids

        if tts_ids:
            # Get chat_id for all operations
            chat_id = context.data.get(CTX_TG_CHAT_ID) or context.data.get("telegram_chat_id")
            
            # Check audio_cleanup config before storing IDs for deletion
            audio_cleanup_enabled = plugins.get_plugin_config('telegram_enhance', agent=self.agent).get('audio_cleanup', True)
            if not audio_cleanup_enabled:
                with open("/tmp/tts_56_trace.log", "a") as _f:
                    _f.write(f"{time.strftime('%H:%M:%S')} _56 audio_cleanup=false, skipping persist\n")
                PrintStyle(font_color="cyan", padding=True).print(
                    "TTS DEBUG _56: audio_cleanup disabled, not storing message IDs"
                )
            else:
                # Persist to file (context.data resets between turns)
                try:
                    from usr.plugins.telegram_enhance.helpers.tts_msg_ids import set_last_tts_msg_ids
                    if chat_id:
                        set_last_tts_msg_ids(int(chat_id), tts_ids)
                        with open("/tmp/tts_56_trace.log", "a") as _f:
                            _f.write(f"{time.strftime('%H:%M:%S')} _56 PERSISTED tts_ids={tts_ids} for chat={chat_id}\n")
                except Exception as e:
                    with open("/tmp/tts_56_trace.log", "a") as _f:
                        _f.write(f"{time.strftime('%H:%M:%S')} _56 persist failed: {e}\n")
            
            # AUTO-REACTION: Add headphones emoji to TTS messages when audio_consolidation is enabled
            _config = plugins.get_plugin_config('telegram_enhance', agent=self.agent)
            audio_consolidation_enabled = _config.get('audio_consolidation', True) if _config else True
            with open("/tmp/tts_56_trace.log", "a") as _f:
                _f.write(f"{time.strftime('%H:%M:%S')} _56 REACT CHECK: config={_config} consolidation={audio_consolidation_enabled} chat_id={chat_id}\n")
            if audio_consolidation_enabled and chat_id:
                bot_name = context.data.get(CTX_TG_BOT)
                with open("/tmp/tts_56_trace.log", "a") as _f:
                    _f.write(f"{time.strftime('%H:%M:%S')} _56 REACT: bot_name={bot_name}, tts_ids={tts_ids}\n")
                if bot_name:
                    # Await the reaction directly (create_task was silently failing)
                    try:
                        await _set_tts_reaction(bot_name, int(chat_id), tts_ids)
                    except Exception as e:
                        with open("/tmp/tts_56_trace.log", "a") as _f:
                            _f.write(f"{time.strftime('%H:%M:%S')} _56 REACT ERROR: {e}\n")
                        PrintStyle.debug(f"TTS REACT: failed to set reaction: {e}")

        # Cleanup
        context.data.pop(CTX_TTS_PENDING_COUNT, None)
