# telegram_enhance hooks.py
#
# Framework runtime hooks called by bot_manager.py during bot creation.
# These run BEFORE start_polling(), so handlers are in place when
# aiogram begins its polling loop.

from helpers.print_style import PrintStyle


def on_bot_created(instance):
    """Called by bot_manager after creating a bot instance, before polling starts.
    
    Registers the message_reaction handler on the bot's dispatcher so that
    user reactions to TTS audio messages are detected for consolidation logic.
    """
    from helpers import plugins
    
    config = plugins.get_plugin_config('telegram_enhance') or {}
    if not config.get('audio_consolidation', True):
        return
    
    try:
        from aiogram import Router
        from aiogram.types import MessageReactionUpdated
    except ImportError:
        return
    
    bot_name = instance.name
    reaction_router = Router()
    
    @reaction_router.message_reaction()
    async def handle_reaction_update(event: MessageReactionUpdated):
        """Handle MessageReactionUpdated events from Telegram."""
        try:
            import time as _time
            chat = event.chat
            message_id = event.message_id
            chat_id = chat.id if chat else None
            
            with open("/tmp/tts_reaction_trace.log", "a") as _f:
                _f.write(f"{_time.strftime('%H:%M:%S')} REACTION FIRED: chat_id={chat_id} msg_id={message_id}\n")
            
            if not chat_id or not message_id:
                return
            
            # Skip bot's own reactions
            user = getattr(event, 'user', None)
            actor = getattr(event, 'actor', None)
            actor_user = user or actor
            if actor_user and getattr(actor_user, 'is_bot', False):
                with open("/tmp/tts_reaction_trace.log", "a") as _f:
                    _f.write(f"{_time.strftime('%H:%M:%S')} REACTION: skipping bot's own reaction\n")
                return
            
            from usr.plugins.telegram_enhance.helpers.tts_heard_state import (
                mark_as_heard, cleanup_old_entries
            )
            
            mark_as_heard(chat_id, message_id)
            PrintStyle(font_color="green", padding=True).print(
                f"TTS REACTION: user reacted to msg {message_id} in chat {chat_id}, marked as listening"
            )
            
            with open("/tmp/tts_reaction_trace.log", "a") as _f:
                _f.write(f"{_time.strftime('%H:%M:%S')} REACTION: marked msg {message_id} in chat {chat_id} as listening\n")
            
            try:
                cleanup_old_entries(chat_id, keep_recent=10)
            except Exception:
                pass
                
        except Exception as e:
            try:
                with open("/tmp/tts_reaction_trace.log", "a") as _f:
                    _f.write(f"REACTION ERROR: {e}\n")
            except Exception:
                pass
            PrintStyle.debug(f"TTS REACTION: handler error: {e}")
    
    # Register on the dispatcher - this is the root that start_polling uses
    instance.dispatcher.include_router(reaction_router)
    PrintStyle(font_color="cyan", padding=True).print(
        f"TTS REACTION: registered handler on bot '{bot_name}' via hooks.py (before polling)"
    )
