# Telegram TTS Prior-Turn Cleanup - monologue_start extension
#
# When the user sends a new message, this extension deletes ALL previous
# TTS audio messages from the prior turn, regardless of reaction state.
# This is the unconditional audio cleanup that keeps the chat tidy.
#
# This is separate from within-turn consolidation logic in _40_tts_response.py
# which uses reaction detection to avoid interrupting active playback.

from helpers.extension import Extension
from helpers.print_style import PrintStyle
from helpers.errors import format_error
from helpers import plugins, files

try:
    from plugins._telegram_integration.helpers.constants import (
        CTX_TG_BOT,
        CTX_TG_CHAT_ID,
        DOWNLOAD_FOLDER,
    )
    _TG_AVAILABLE = True
except ImportError:
    _TG_AVAILABLE = False


class TtsPriorTurnCleanup(Extension):
    
    async def execute(self, **kwargs):
        if not _TG_AVAILABLE:
            return
        if not self.agent or self.agent.number != 0:
            return
        
        context = self.agent.context
        if not context.data.get(CTX_TG_BOT):
            return
        
        chat_id = context.data.get(CTX_TG_CHAT_ID)
        if not chat_id:
            return
        chat_id_int = int(chat_id)
        
        # Check if audio cleanup is enabled
        config = plugins.get_plugin_config("telegram_enhance", agent=self.agent) or {}
        audio_cleanup_enabled = config.get('audio_cleanup', True)
        if not audio_cleanup_enabled:
            return
        
        # Get previous TTS message IDs from persistent storage
        prev_ids = None
        try:
            from usr.plugins.telegram_enhance.helpers.tts_msg_ids import (
                get_last_tts_msg_ids, clear_last_tts_msg_ids
            )
            prev_ids = get_last_tts_msg_ids(chat_id_int)
        except Exception:
            return
        
        if not prev_ids:
            return
        
        # Delete all previous TTS audio messages unconditionally
        bot_name = context.data.get(CTX_TG_BOT)
        if not bot_name:
            return
        
        try:
            from plugins._telegram_integration.helpers.bot_manager import get_bot
            instance = get_bot(bot_name)
            if not instance:
                return
            
            from aiogram import Bot
            from contextlib import asynccontextmanager
            
            @asynccontextmanager
            async def _temp_bot(token: str):
                bot = Bot(token=token)
                try:
                    yield bot
                finally:
                    try:
                        await bot.session.close()
                    except Exception:
                        pass
            
            deleted = 0
            async with _temp_bot(instance.bot.token) as bot:
                for msg_id in prev_ids:
                    try:
                        await bot.delete_message(chat_id=chat_id_int, message_id=msg_id)
                        deleted += 1
                    except Exception:
                        pass
            
            if deleted > 0:
                PrintStyle(font_color="cyan", padding=True).print(
                    f"TTS CLEANUP: deleted {deleted} prior-turn audio messages in chat {chat_id_int}"
                )
            
            # Clear persisted IDs
            clear_last_tts_msg_ids(chat_id_int)
            
        except Exception as e:
            PrintStyle.debug(f"TTS CLEANUP: error deleting prior-turn audio: {format_error(e)}")
