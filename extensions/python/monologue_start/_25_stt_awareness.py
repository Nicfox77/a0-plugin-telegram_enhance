"""STT Awareness Extension

Injects a system reminder when processing voice transcription messages,
noting potential transcription errors and encouraging clarification.
"""
from helpers.extension import Extension
from helpers.print_style import PrintStyle

STT_REMINDER = (
    "The user's message was automatically transcribed from audio/speech. "
    "There may be transcription errors, especially with proper nouns, "
    "technical terms, product names, and uncommon words. "
    "If anything in the message seems unclear, misspelled, or incorrect, "
    "do not assume the literal transcription is accurate. "
    "Instead, use context to infer the likely intended meaning. "
    "If you cannot confidently determine the intended meaning, "
    "politely ask the user for clarification rather than guessing."
)


class SttAwareness(Extension):

    async def execute(self, **kwargs):
        if not self.agent:
            return

        try:
            # Check the last user message for voice transcription markers
            history = self.agent.history
            if not history:
                return

            # Find the most recent user message
            for msg in reversed(history):
                if getattr(msg, 'role', '') == 'user' or not getattr(msg, 'ai', True):
                    text = getattr(msg, 'content', '') or getattr(msg, 'text', '') or ""
                    if isinstance(text, list):
                        text = " ".join(
                            item.get("text", "") if isinstance(item, dict) else str(item)
                            for item in text
                        )
                    text_lower = text.lower()

                    if any(marker in text_lower for marker in [
                        "[microphone]",
                        "voice transcription:",
                        "voice message",
                        "audio message"
                    ]):
                        # Inject the STT awareness reminder into extras_persistent
                        if not hasattr(self.agent, 'extras_persistent'):
                            self.agent.extras_persistent = {}
                        self.agent.extras_persistent['stt_awareness'] = STT_REMINDER
                        PrintStyle(font_color="cyan", padding=True).print(
                            "STT awareness: voice transcription detected"
                        )
                    break  # Only check the most recent user message

        except Exception as e:
            PrintStyle.debug(f"STT awareness check failed: {e}")
