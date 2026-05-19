# Telegram TTS Response - process_chain_end extension
#
# When the agent responds to a Telegram conversation and TTS is enabled,
# this extension converts the text response to audio and adds it as an
# attachment so the telegram reply extension sends it as a voice message.
#
# ACCUMULATION MODE: When the agent sends multiple responses per turn
# (break_loop: false), this extension accumulates ALL response texts
# and generates a single audio file from the full accumulated text.
# Each firing deletes the previous audio message and sends the updated one.
# The accumulator is cleared at monologue_start (new user message).
#
# When delete_previous_tts_audio is enabled (default), previous TTS audio
# messages are deleted before the new one is sent, preventing audio pileup.
#
# Priority 40 runs before the built-in telegram reply at priority 55.

import asyncio
import os
import uuid
import time as _time

from contextlib import asynccontextmanager
from helpers.extension import Extension
from helpers.print_style import PrintStyle
from helpers.errors import format_error
from helpers import plugins, files
from agent import AgentContext, LoopData

try:
    from plugins._telegram_integration.helpers.constants import (
        CTX_TG_BOT,
        CTX_TG_CHAT_ID,
        CTX_TG_ATTACHMENTS,
        DOWNLOAD_FOLDER,
    )
    _TG_AVAILABLE = True
except ImportError:
    _TG_AVAILABLE = False

# Context data keys
CTX_TTS_LAST_MSG_IDS = "_tg_last_tts_message_ids"
CTX_TTS_PENDING_COUNT = "_tg_tts_pending_attachment_count"


def _extract_all_responses(context: AgentContext) -> str:
    """Extract and combine ALL response texts from the current turn only."""
    with context.log._lock:
        logs = list(context.log.logs)
    if not logs:
        return ""
    # Find the last user message to界定 the current turn
    last_user_idx = -1
    for i in range(len(logs) - 1, -1, -1):
        if logs[i].type == "user":
            last_user_idx = i
            break
    # Collect response texts only after the last user message
    responses = []
    for item in logs[last_user_idx + 1:]:
        if item.type == "response" and item.content and item.content.strip():
            responses.append(item.content.strip())
    if not responses:
        return ""
    # Join with a period and space for natural TTS reading
    return ". ".join(responses)


def _extract_last_response(context: AgentContext) -> str:
    """Extract ONLY the LAST response text from the current turn."""
    with context.log._lock:
        logs = list(context.log.logs)
    if not logs:
        return ""
    # Find the last user message to界定 the current turn
    last_user_idx = -1
    for i in range(len(logs) - 1, -1, -1):
        if logs[i].type == "user":
            last_user_idx = i
            break
    # Find the last response after the last user message
    for item in reversed(logs[last_user_idx + 1:]):
        if item.type == "response" and item.content and item.content.strip():
            return item.content.strip()
    return ""


async def _delete_previous_tts_audio(context: AgentContext, bot_name: str, chat_id: int):
    """Delete previous TTS audio messages from Telegram chat."""
    prev_ids = context.data.pop(CTX_TTS_LAST_MSG_IDS, None)
    if not prev_ids:
        return

    from plugins._telegram_integration.helpers.bot_manager import get_bot
    instance = get_bot(bot_name)
    if not instance:
        return

    from aiogram import Bot
    from aiogram.client.default import DefaultBotProperties

    try:
        async with _temp_bot(instance.bot.token) as bot:
            for msg_id in prev_ids:
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=msg_id)
                except Exception:
                    # Message already deleted or not found - ignore silently
                    pass
    except Exception as e:
        PrintStyle.debug(f"Telegram TTS: cleanup error (non-fatal): {format_error(e)}")


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


class TtsResponse(Extension):

    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        if not self.agent or self.agent.number != 0:
            return

        if not _TG_AVAILABLE:
            return

        context = self.agent.context
        if not context.data.get(CTX_TG_BOT):
            return

        # Load plugin config
        config = plugins.get_plugin_config("telegram_enhance", agent=self.agent) or {}

        # Check per-chat TTS override
        per_chat_tts = context.data.get('_tg_tts_enabled')
        if per_chat_tts is None:
            # Fallback to persistent storage
            try:
                from usr.plugins.telegram_enhance.helpers.tts_state import get_tts_enabled
                chat_id = context.data.get(CTX_TG_CHAT_ID)
                if chat_id is not None:
                    per_chat_tts = get_tts_enabled(chat_id)
            except Exception:
                pass
            if per_chat_tts is None:
                if not config.get('tts_enabled', False):
                    return
            elif not per_chat_tts:
                return
        elif not per_chat_tts:
            return

        # Get chat_id for accumulator operations
        chat_id = context.data.get(CTX_TG_CHAT_ID)
        if not chat_id:
            return
        chat_id_int = int(chat_id)

        # Load audio management settings
        audio_cleanup_enabled = config.get('audio_cleanup', True)
        audio_consolidation_enabled = config.get('audio_consolidation', True)
        delete_enabled = config.get('delete_previous_tts_audio', True) if audio_cleanup_enabled else False
        
        # STEP 1: Check reaction state BEFORE deciding deletion or consolidation
        # If user reacted to previous TTS → they are actively listening → preserve that clip
        user_is_listening = False
        prev_ids = None
        try:
            from usr.plugins.telegram_enhance.helpers.tts_msg_ids import get_last_tts_msg_ids
            prev_ids = get_last_tts_msg_ids(chat_id_int)
        except Exception:
            pass
        
        if prev_ids and audio_consolidation_enabled:
            try:
                from usr.plugins.telegram_enhance.helpers.tts_heard_state import is_heard
                user_is_listening = any(is_heard(chat_id_int, msg_id) for msg_id in prev_ids)
                if user_is_listening:
                    PrintStyle(font_color="yellow", padding=True).print(
                        f"TTS REACTION: user is listening ({prev_ids}), keeping clips separate"
                    )
            except Exception as e:
                PrintStyle.debug(f"TTS REACTION: check failed, defaulting to consolidate: {e}")
        
        # STEP 2: Delete previous TTS audio messages if configured
        # Skip deletion ONLY if user is actively listening (reacted to the clip)
        if delete_enabled and not user_is_listening:
            if prev_ids:
                bot_name = context.data.get(CTX_TG_BOT)
                if bot_name and chat_id:
                    try:
                        from plugins._telegram_integration.helpers.bot_manager import get_bot
                        instance = get_bot(bot_name)
                        if instance:
                            async with _temp_bot(instance.bot.token) as bot:
                                for msg_id in prev_ids:
                                    try:
                                        await bot.delete_message(chat_id=chat_id_int, message_id=msg_id)
                                    except Exception:
                                        pass
                            from usr.plugins.telegram_enhance.helpers.tts_msg_ids import clear_last_tts_msg_ids
                            clear_last_tts_msg_ids(chat_id_int)
                    except Exception:
                        pass
        
        # STEP 3: Extract response text based on consolidation and listening state
        if audio_consolidation_enabled and not user_is_listening:
            # User hasn't seen previous message → consolidate everything into one clip
            response_text = _extract_all_responses(context)
        else:
            # User is listening OR consolidation is off → only send new content
            response_text = _extract_last_response(context)
        if not response_text or not response_text.strip():
            return

        # Truncate very long responses for TTS
        max_chars = 4096
        if len(response_text) > max_chars:
            response_text = response_text[:max_chars]

        # Apply per-chat voice override
        tts_config = dict(config)
        per_chat_voice = context.data.get('_tg_tts_voice')
        if per_chat_voice:
            provider_name = tts_config.get('tts_provider', 'kokoro')
            if provider_name == 'kokoro':
                tts_config['kokoro_voice'] = per_chat_voice
            elif provider_name == 'openai':
                tts_config['tts_openai_voice'] = per_chat_voice
            elif provider_name == 'edge_tts':
                tts_config['tts_edge_voice'] = per_chat_voice

        # Instantiate TTS provider
        try:
            from usr.plugins.telegram_enhance.helpers.providers import get_tts_provider
            provider_name = tts_config.get('tts_provider', 'kokoro')
            provider = get_tts_provider(provider_name, tts_config)
        except Exception as e:
            PrintStyle.error(f"Telegram TTS: failed to initialise provider: {format_error(e)}")
            return

        # Prepare output path
        download_dir = files.get_abs_path(DOWNLOAD_FOLDER)
        os.makedirs(download_dir, exist_ok=True)
        audio_filename = "tts_" + uuid.uuid4().hex + ".mp3"
        audio_path = os.path.join(download_dir, audio_filename)

        # Synthesize speech in executor to avoid blocking the async loop
        try:
            await asyncio.get_event_loop().run_in_executor(
                None, provider.synthesize, response_text, audio_path
            )
        except Exception as e:
            PrintStyle.error(f"Telegram TTS: synthesis error: {format_error(e)}")
            return

        # Verify the file was created
        if not os.path.isfile(audio_path):
            return

        # Add the audio file to telegram attachments
        docker_path = files.get_abs_path_dockerized(audio_path)
        attachments = context.data.get(CTX_TG_ATTACHMENTS)
        if not isinstance(attachments, list):
            attachments = []
            context.data[CTX_TG_ATTACHMENTS] = attachments

        # Record how many attachments existed before we add ours
        pre_count = len(attachments)
        attachments.append(docker_path)

        # Tell _56 how many TTS attachments we added (for msg_id tracking)
        tts_count = len(attachments) - pre_count  # always 1, but future-proof
        context.data[CTX_TTS_PENDING_COUNT] = context.data.get(CTX_TTS_PENDING_COUNT, 0) + tts_count
