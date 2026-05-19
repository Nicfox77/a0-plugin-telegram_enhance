import asyncio
import json
import os
from typing import Any

from helpers.extension import Extension
from helpers.print_style import PrintStyle
from helpers import files as files_helper

_REGISTERED_BOTS: set[str] = set()

# Our supported commands
_VOICE_COMMANDS = {
    '/tts', '/tts_voice', '/stt', '/voice_help',
    '/attach', '/detach', '/chats',
}


class TelegramVoiceCommands(Extension):
    async def execute(self, **kwargs):
        try:
            from plugins._telegram_integration.helpers.bot_manager import get_all_bots
        except ImportError:
            return

        bots = get_all_bots()
        for name, instance in bots.items():
            if name in _REGISTERED_BOTS:
                continue
            try:
                # Register outer middleware that intercepts our commands
                # BEFORE the catch-all on_message handler can swallow them
                middleware = _VoiceCommandMiddleware(name)
                instance.router.message.outer_middleware(middleware)

                # Register commands in Telegram's autocomplete menu
                asyncio.ensure_future(_register_bot_commands(instance))

                _REGISTERED_BOTS.add(name)
                PrintStyle.info(f"Telegram Voice Commands: registered middleware + menu for bot '{name}'")
            except Exception as e:
                PrintStyle.error(f"Telegram Voice Commands: failed to register for bot '{name}': {e}")


class _VoiceCommandMiddleware:
    """Aiogram outer middleware that intercepts voice/TG commands before the catch-all handler."""

    def __init__(self, bot_name: str):
        self.bot_name = bot_name

    async def __call__(self, handler, event, data):
        text = getattr(event, 'text', '') or ''
        if text.startswith('/'):
            # Extract the command (handle @bot_name suffix)
            parts = text.split()
            cmd = parts[0].lower().split('@')[0]
            if cmd in _VOICE_COMMANDS:
                try:
                    await _dispatch_command(cmd.lstrip('/'), event, self.bot_name)
                except Exception as e:
                    PrintStyle.error(f"Voice command {cmd} error: {e}")
                # Return None — don't propagate to the catch-all handler
                return
        # Not our command — pass through to normal handler chain
        return await handler(event, data)


async def _register_bot_commands(instance):
    """Register our commands in Telegram's autocomplete menu, merging with existing ones."""
    try:
        from aiogram.types import BotCommand

        # Fetch existing commands so we don't overwrite defaults like /start, /clear
        existing = await instance.bot.get_my_commands()
        existing_cmds = {c.command for c in existing}

        our_commands = [
            BotCommand(command='tts', description='Toggle voice responses on/off'),
            BotCommand(command='tts_voice', description='Change TTS voice'),
            BotCommand(command='stt', description='Show STT settings'),
            BotCommand(command='chats', description='List available chats'),
            BotCommand(command='attach', description='Attach to a chat by name'),
            BotCommand(command='detach', description='Detach from linked chat'),
            BotCommand(command='voice_help', description='Show all voice commands'),
        ]

        # Merge: keep existing commands, add ours (don't overwrite if same name)
        our_cmd_names = {c.command for c in our_commands}
        merged = [c for c in existing if c.command not in our_cmd_names]
        merged.extend(our_commands)

        await instance.bot.set_my_commands(merged)
        PrintStyle.info(f"Telegram ({instance.name}): registered command menu")
    except Exception as e:
        PrintStyle.error(f"Telegram ({instance.name}): failed to set command menu: {e}")


def _list_all_chats() -> list[dict]:
    """Scan chat directories and return list of {id, name}."""
    chats_dir = files_helper.get_abs_path("usr/chats")
    if not os.path.isdir(chats_dir):
        return []
    chats = []
    for entry in sorted(os.listdir(chats_dir)):
        chat_json_path = os.path.join(chats_dir, entry, "chat.json")
        if not os.path.isfile(chat_json_path):
            continue
        try:
            with open(chat_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            ctx_id = data.get("id", entry)
            name = data.get("name", "") or ctx_id
            chats.append({"id": ctx_id, "name": name})
        except Exception:
            continue
    return chats


def _resolve_context_id(arg: str):
    """Resolve a context ID or chat name to a context ID.

    Returns (context_id, error_message). If found, error is None.
    """
    from agent import AgentContext

    # Try as exact context ID first
    ctx = AgentContext.get(arg)
    if ctx:
        return arg, None

    # Try as chat name (case-insensitive)
    all_chats = _list_all_chats()
    matches = [c for c in all_chats if c["name"].lower() == arg.lower()]
    if len(matches) == 1:
        ctx_id = matches[0]["id"]
        ctx = AgentContext.get(ctx_id)
        if ctx:
            return ctx_id, None

    # Try partial name match (case-insensitive)
    partial = [c for c in all_chats if arg.lower() in c["name"].lower()]
    if len(partial) == 1:
        ctx_id = partial[0]["id"]
        ctx = AgentContext.get(ctx_id)
        if ctx:
            return ctx_id, None
    elif len(partial) > 1:
        names = ', '.join(f"'{c['name']}'" for c in partial)
        return None, f"Multiple chats match '{arg}': {names}. Be more specific."

    return None, f"Chat '{arg}' not found. Use /chats to list available chats."


async def _dispatch_command(command: str, message, bot_name: str):
    from plugins._telegram_integration.helpers.handler import _load_state, _save_state, _map_key, _send_with_temp_bot
    from plugins._telegram_integration.helpers.bot_manager import get_bot
    from agent import AgentContext
    from helpers import plugins as plugin_helpers

    instance = get_bot(bot_name)
    if not instance:
        return

    # Load the bot config from telegram integration plugin
    tg_config = plugin_helpers.get_plugin_config('_telegram_integration') or {}
    bots_cfg = tg_config.get('bots') or []
    bot_cfg = {}
    for b in bots_cfg:
        if b.get('name') == bot_name:
            bot_cfg = b
            break

    config = plugin_helpers.get_plugin_config('telegram_enhance') or {}
    user = message.from_user
    if not user:
        return

    # Find current context for this chat
    state = _load_state()
    key = _map_key(bot_name, user.id, message.chat.id)
    ctx_id = state.get('chats', {}).get(key)
    ctx = AgentContext.get(ctx_id) if ctx_id else None

    token = instance.bot.token
    chat_id = message.chat.id

    if command == 'voice_help':
        help_text = (
            "\U0001f399 Voice Commands:\n\n"
            "/tts - Toggle voice responses on/off\n"
            "/tts_voice <name> - Change TTS voice\n"
            "/stt - Show current STT settings\n"
            "/attach <name_or_id> - Link to existing chat\n"
            "/detach - Unlink from attached context\n"
            "/chats - List all available chats\n"
            "/voice_help - Show this help"
        )
        await _send_with_temp_bot(token, chat_id, help_text, parse_mode=None)

    elif command == 'chats':
        all_chats = _list_all_chats()
        if not all_chats:
            await _send_with_temp_bot(token, chat_id, 'No chats found.', parse_mode=None)
            return
        lines = ["\U0001f4cb Available Chats:\n"]
        for i, c in enumerate(all_chats, 1):
            name = c["name"]
            ctx_id_short = c["id"]
            if name == ctx_id_short:
                lines.append(f"{i}. {name}")
            else:
                lines.append(f"{i}. {name} (ID: {ctx_id_short})")
        lines.append("\nUse /attach <name> or /attach <id> to link.")
        await _send_with_temp_bot(token, chat_id, "\n".join(lines), parse_mode=None)

    elif command == 'tts':
        if not ctx:
            await _send_with_temp_bot(token, chat_id, 'No active chat context. Send a message first.', parse_mode=None)
            return
        current = ctx.data.get('_tg_tts_enabled')
        if current is None:
            current = config.get('tts_enabled', False)
        new_val = not current
        ctx.data['_tg_tts_enabled'] = new_val
        # Persist to disk so the setting survives restarts
        try:
            from usr.plugins.telegram_enhance.helpers.tts_state import set_tts_enabled
            set_tts_enabled(str(chat_id), new_val)
        except Exception:
            pass
        status = 'enabled \u2705' if new_val else 'disabled \u274c'
        await _send_with_temp_bot(token, chat_id, f'TTS {status}', parse_mode=None)

    elif command == 'tts_voice':
        if not ctx:
            await _send_with_temp_bot(token, chat_id, 'No active chat context. Send a message first.', parse_mode=None)
            return
        args = (message.text or '').split(maxsplit=1)
        if len(args) < 2:
            # Show available voices
            tts_provider = ctx.data.get('_tg_tts_voice') or config.get('tts_provider', 'kokoro')
            current_voice = ctx.data.get('_tg_tts_voice')
            if current_voice is None:
                # Get from global config based on provider
                if tts_provider == 'kokoro':
                    current_voice = config.get('kokoro_voice', 'af_sky')
                elif tts_provider == 'openai':
                    current_voice = config.get('tts_openai_voice', 'alloy')
                elif tts_provider == 'edge_tts':
                    current_voice = config.get('tts_edge_voice', 'en-US-AvaNeural')
                else:
                    current_voice = 'unknown'
            await _send_with_temp_bot(
                token, chat_id,
                f'Current voice: {current_voice}\nUsage: /tts_voice <name>',
                parse_mode=None
            )
            return
        voice_name = args[1].strip()
        ctx.data['_tg_tts_voice'] = voice_name
        # Persist to disk so the setting survives restarts
        try:
            from usr.plugins.telegram_enhance.helpers.tts_state import set_tts_voice
            set_tts_voice(str(chat_id), voice_name)
        except Exception:
            pass
        await _send_with_temp_bot(token, chat_id, f'TTS voice set to: {voice_name}', parse_mode=None)

    elif command == 'stt':
        stt_provider = config.get('stt_provider', 'parakeet')
        language = config.get('language') or 'auto-detect'
        keyterms = config.get('keyterms') or []
        keyterms_str = ', '.join(keyterms) if keyterms else 'none'
        info = (
            f'STT Provider: {stt_provider}\n'
            f'Language: {language}\n'
            f'Keyterms: {keyterms_str}'
        )
        await _send_with_temp_bot(token, chat_id, info, parse_mode=None)

    elif command == 'attach':
        args = (message.text or '').split(maxsplit=1)
        if len(args) < 2:
            await _send_with_temp_bot(
                token, chat_id,
                'Usage: /attach <name_or_id>\nUse /chats to list available chats by name.',
                parse_mode=None
            )
            return
        arg = args[1].strip()
        context_id, err = _resolve_context_id(arg)
        if err:
            await _send_with_temp_bot(token, chat_id, err, parse_mode=None)
            return
        target_ctx = AgentContext.get(context_id)
        if not target_ctx:
            await _send_with_temp_bot(token, chat_id, f'Context {context_id} not found.', parse_mode=None)
            return
        # Update telegram state mapping
        from plugins._telegram_integration.helpers.constants import (
            CTX_TG_BOT, CTX_TG_BOT_CFG, CTX_TG_CHAT_ID, CTX_TG_USER_ID, CTX_TG_USERNAME
        )

        # Clean up old context if this Telegram session pointed elsewhere
        old_ctx_id = state.get('chats', {}).get(key)
        if old_ctx_id and old_ctx_id != context_id:
            old_ctx = AgentContext.get(old_ctx_id)
            if old_ctx:
                for k in (CTX_TG_BOT, CTX_TG_BOT_CFG, CTX_TG_CHAT_ID, CTX_TG_USER_ID, CTX_TG_USERNAME):
                    old_ctx.data.pop(k, None)

        state.setdefault('chats', {})[key] = context_id
        _save_state(state)
        target_ctx.data[CTX_TG_BOT] = bot_name
        target_ctx.data[CTX_TG_BOT_CFG] = bot_cfg
        target_ctx.data[CTX_TG_CHAT_ID] = message.chat.id
        target_ctx.data[CTX_TG_USER_ID] = user.id
        target_ctx.data[CTX_TG_USERNAME] = user.username or ''
        # Get the chat name for the confirmation message
        chat_name = arg
        all_chats = _list_all_chats()
        for c in all_chats:
            if c["id"] == context_id:
                chat_name = c["name"]
                break
        await _send_with_temp_bot(token, chat_id, f'\u2705 Attached to \'{chat_name}\' ({context_id})', parse_mode=None)

    elif command == 'detach':
        if not ctx_id:
            await _send_with_temp_bot(token, chat_id, 'No active attachment found.', parse_mode=None)
            return
        state = _load_state()
        chats = state.get('chats', {})
        old_ctx_id = chats.pop(key, None)
        if old_ctx_id:
            # Clean up context data
            old_ctx = AgentContext.get(old_ctx_id)
            if old_ctx:
                from plugins._telegram_integration.helpers.constants import (
                    CTX_TG_BOT, CTX_TG_BOT_CFG, CTX_TG_CHAT_ID, CTX_TG_USER_ID, CTX_TG_USERNAME
                )
                for k in (CTX_TG_BOT, CTX_TG_BOT_CFG, CTX_TG_CHAT_ID, CTX_TG_USER_ID, CTX_TG_USERNAME):
                    old_ctx.data.pop(k, None)
            _save_state(state)
            await _send_with_temp_bot(
                token, chat_id,
                f'Detached from \'{old_ctx_id}\'. Send a message to create a new chat.',
                parse_mode=None
            )
        else:
            await _send_with_temp_bot(token, chat_id, 'No active attachment found.', parse_mode=None)
