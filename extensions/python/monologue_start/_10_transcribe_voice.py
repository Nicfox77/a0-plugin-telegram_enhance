# Telegram Voice Transcription - monologue_start extension
#
# Detects audio/voice attachments on the last user message when the conversation
# originates from the Telegram integration, transcribes them with the configured
# STT provider, and appends the transcription text to the message content so the
# agent can read it.
#
# Supported STT providers:
#   - openai   : OpenAI Whisper API
#   - xai      : X.ai Grok STT API
#   - parakeet : Local NVIDIA Parakeet ONNX (CPU)

import asyncio
import os
from typing import Any

from helpers.extension import Extension
from helpers.print_style import PrintStyle
from helpers import plugins, files

# Audio file extensions we consider transcribable
AUDIO_EXTENSIONS = {".ogg", ".mp3", ".wav", ".m4a", ".flac", ".webm"}


def _get_audio_attachments(attachments: list[str]) -> list[str]:
    """Return only the attachment paths that look like audio files."""
    return [
        p for p in attachments
        if os.path.splitext(p)[1].lower() in AUDIO_EXTENSIONS
    ]


def _is_raw_message(content: Any) -> bool:
    """Check if content is a RawMessage wrapper (has raw_content key)."""
    return (
        isinstance(content, dict)
        and "raw_content" in content
        and "preview" in content
    )


def _unpack_content(content: Any) -> dict:
    """Unwrap content, handling RawMessage wrappers."""
    if _is_raw_message(content):
        raw = content.get("raw_content")
        if isinstance(raw, list) and len(raw) == 1:
            return raw[0] if isinstance(raw[0], dict) else {}
        return {}
    if isinstance(content, dict):
        return content
    return {}


def _get_stt_provider(config: dict):
    """Instantiate the configured STT provider."""
    from usr.plugins.telegram_enhance.helpers.providers import get_stt_provider
    provider_name = config.get("stt_provider", "openai")
    return get_stt_provider(provider_name, config)


class TranscribeVoice(Extension):

    async def execute(self, loop_data=None, **kwargs):
        PrintStyle.info("Telegram Voice: monologue_start extension triggered")
        if not self.agent:
            PrintStyle.warning("Telegram Voice: no agent, skipping")
            return

        # Import here to avoid hard dependency at module level
        try:
            from plugins._telegram_integration.helpers.constants import CTX_TG_BOT
        except ImportError:
            PrintStyle.warning("Telegram Voice: telegram constants not available")
            return  # Telegram plugin not installed

        context = self.agent.context

        # Only act on Telegram-originated conversations
        if not context.data.get(CTX_TG_BOT):
            PrintStyle.warning(f"Telegram Voice: not a TG context (CTX_TG_BOT={context.data.get(CTX_TG_BOT)})")
            return

        # Determine the last user message to inspect
        msg = getattr(loop_data, "user_message", None) if loop_data else None
        if msg is None:
            msg = getattr(self.agent, "last_user_message", None)
        if msg is None:
            PrintStyle.warning("Telegram Voice: no user message found")
            return

        # Avoid re-transcribing on subsequent monologue iterations
        transcribed_key = "_tg_voice_transcribed"
        if context.data.get(transcribed_key) == msg.id:
            PrintStyle.info("Telegram Voice: already transcribed, skipping")
            return

        PrintStyle.info(f"Telegram Voice: processing message {msg.id}, content type={type(msg.content).__name__}")

        # Unpack message content
        content = _unpack_content(msg.content)
        if not content:
            PrintStyle.warning(f"Telegram Voice: content unpacked to empty, raw type={type(msg.content).__name__}")
            return

        PrintStyle.info(f"Telegram Voice: content keys={list(content.keys()) if isinstance(content, dict) else 'not a dict'}")

        attachments = content.get("attachments")
        if not isinstance(attachments, list) or not attachments:
            PrintStyle.warning(f"Telegram Voice: no attachments found (attachments={attachments}, type={type(attachments).__name__})")
            return

        audio_paths = _get_audio_attachments(attachments)
        PrintStyle.info(f"Telegram Voice: found {len(audio_paths)} audio files: {audio_paths}")
        if not audio_paths:
            return

        # Load plugin config
        config = plugins.get_plugin_config("telegram_enhance", agent=self.agent) or {}
        language = config.get("language")  # None = auto-detect
        include_original = config.get("include_original_attachment", True)
        keyterms = config.get('keyterms') or []

        # Instantiate STT provider
        try:
            provider = _get_stt_provider(config)
        except Exception as e:
            PrintStyle.error(f"Telegram Voice: failed to initialise STT provider: {e}")
            return

        # Transcribe each audio file
        transcriptions: list[str] = []
        remaining_attachments: list[str] = []

        for audio_path in audio_paths:
            local_path = files.fix_dev_path(audio_path)

            if not os.path.isfile(local_path):
                PrintStyle.warning(f"Telegram Voice: audio file not found: {local_path}")
                remaining_attachments.append(audio_path)
                continue

            try:
                transcription = await asyncio.get_event_loop().run_in_executor(
                    None, provider.transcribe, local_path, language, keyterms
                )
            except Exception as e:
                provider_name = type(provider).__name__
                PrintStyle.error(f"Telegram Voice: STT error ({provider_name}): {e}")
                remaining_attachments.append(audio_path)
                continue

            if transcription and transcription.strip():
                transcriptions.append(transcription.strip())
                basename = os.path.basename(local_path)
                chars = len(transcription)
                provider_name = type(provider).__name__
                PrintStyle.info(
                    f"Telegram Voice: transcribed {basename} ({chars} chars) via {provider_name}"
                )
            else:
                transcriptions.append("[inaudible / empty transcription]")
                basename = os.path.basename(local_path)
                PrintStyle.warning(f"Telegram Voice: empty transcription for {basename}")

            if include_original:
                remaining_attachments.append(audio_path)

        if not transcriptions:
            return

        # Build transcription text
        transcription_text = "\n\n".join(transcriptions)
        existing_message = content.get("user_message", "")

        # Replace voice/video placeholders with transcription text
        voice_placeholder = "[Voice message — see attachment]"
        video_placeholder = "[Video note — see attachment]"
        voice_replacement = f"(voice) {transcription_text}"

        new_message = existing_message.replace(voice_placeholder, voice_replacement)
        new_message = new_message.replace(video_placeholder, voice_replacement)

        # If no placeholder found (edge case), fall back to append
        if new_message == existing_message:
            new_message = (
                existing_message + "\n\n"
                "---\n"
                "[microphone] **Voice transcription:**\n" + transcription_text
            )

        content["user_message"] = new_message

        # Update attachments list (remove audio if include_original is false)
        non_audio = [p for p in attachments if p not in audio_paths]
        content["attachments"] = non_audio + remaining_attachments

        # --- Update LogItem so chat history persists the transcription ---
        # The LogItem was created by log_user_message() with the placeholder text.
        # Without this update, saved chat files still show the useless placeholder.
        try:
            log = context.log
            target_item = None
            with log._lock:
                for log_item in reversed(log.logs):
                    if log_item.id == msg.id:
                        target_item = log_item
                        break

            if target_item and target_item.content:
                log_content = target_item.content
                updated_log = log_content.replace(voice_placeholder, voice_replacement)
                updated_log = updated_log.replace(video_placeholder, voice_replacement)
                if updated_log != log_content:
                    target_item.update(content=updated_log)
                    PrintStyle.info(
                        f"Telegram Voice: updated LogItem {msg.id} with transcription"
                    )
        except Exception as e:
            PrintStyle.warning(f"Telegram Voice: failed to update LogItem: {e}")

        # Mark as transcribed to avoid re-processing on subsequent iterations
        context.data[transcribed_key] = msg.id

        PrintStyle.success(
            f"Telegram Voice: replaced placeholder with transcription in message {msg.id}"
        )
