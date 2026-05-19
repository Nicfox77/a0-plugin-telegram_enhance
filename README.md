# Telegram Enhance

Automatically transcribes voice messages received via the Telegram bot integration using multiple STT providers, and optionally responds with TTS voice messages.

## Features

### Speech-to-Text (STT)
Transcribe incoming Telegram voice messages using one of three providers:

- **OpenAI Whisper** – Cloud API, high accuracy, multi-language
- **X.ai Grok STT** – Cloud API, competitive pricing, keyterm biasing
- **Local Parakeet ONNX** – CPU-optimized local inference via NVIDIA Parakeet, no API key needed

### Text-to-Speech (TTS)
Automatically convert agent text responses to voice messages sent back on Telegram:

- **Kokoro ONNX** – Local CPU inference, high-quality voices, no API key needed (default)
- **OpenAI TTS** – High-quality voices (alloy, echo, fable, onyx, nova, shimmer)
- **Edge TTS** – Free, no API key required, many voice options
- **NeuTTS Air** – Neuphonic TTS with optional voice cloning

### Custom Keyterms
Bias STT transcription with custom words/phrases (e.g. product names, technical terms).
Supported by X.ai (native keyterm API) and OpenAI (prompt parameter). Not supported by Parakeet.

### Telegram Commands
Control voice features directly from Telegram:
- `/tts` – Toggle TTS on/off for current chat
- `/tts_voice <name>` – Change TTS voice for current chat
- `/stt` – Show current STT settings
- `/attach <context_id>` – Link to an existing web chat context
- `/detach` – Unlink from attached context
- `/voice_help` – Show all voice commands

## Requirements

### Core
- `openai>=1.0.0`
- `requests>=2.28.0`

### Optional (Parakeet STT)
- `onnxruntime>=1.16.0`
- `onnx-asr>=0.7.0`
- `soundfile>=0.12.0`
- `librosa>=0.10.0`

### Optional (Edge TTS)
- `edge-tts>=6.1.0`

### Optional (Kokoro TTS)
- `kokoro-onnx>=0.4.0`
- `soundfile>=0.12.0`
- `onnxruntime>=1.16.0`

### Optional (NeuTTS Air)
- `neuttsair`

## How It Works

### STT (monologue_start extension)

When a Telegram user sends a voice message:

1. The built-in `_telegram_integration` plugin downloads the voice as an `.ogg` file.
2. This extension detects audio attachments in the last user message.
3. It transcribes them using the configured STT provider.
4. The transcription text is appended to the user message so the agent can read it.

### TTS (process_chain_end extension, priority 40)

When the agent generates a response:

1. The TTS extension checks if the conversation is from Telegram and TTS is enabled (globally or per-chat).
2. It extracts the agent's last response text.
3. Generates audio via the configured TTS provider.
4. Adds the audio file to the Telegram attachments list.
5. The built-in telegram reply extension (priority 55) sends it as a voice message.

### Telegram Commands (job_loop extension)

Registers additional command handlers on the Telegram bot router:
- Per-chat TTS toggle stored in `context.data['_tg_tts_enabled']`
- Per-chat voice override stored in `context.data['_tg_tts_voice']`
- Context attachment via `/attach` for linking Telegram to web chat sessions

## Configuration

| Setting | Default | Description |
|---|---|---|
| `stt_provider` | `parakeet` | STT provider: `openai`, `xai`, `parakeet` |
| `language` | `null` | Language hint (`null` = auto-detect) |
| `keyterms` | `[]` | Custom words to bias STT transcription |
| `include_original_attachment` | `true` | Keep audio file after transcription |
| `openai_model` | `whisper-1` | OpenAI Whisper model name |
| `openai_api_key` | `null` | OpenAI API key (env fallback) |
| `xai_api_key` | `null` | X.ai API key (env fallback) |
| `parakeet_model` | `nemo-parakeet-tdt-0.6b-v3` | onnx-asr model identifier |
| `tts_enabled` | `false` | Enable automatic voice responses |
| `tts_provider` | `kokoro` | TTS provider: `kokoro`, `openai`, `edge_tts`, `neutts` |
| `tts_openai_model` | `tts-1` | OpenAI TTS model name |
| `tts_openai_voice` | `alloy` | OpenAI TTS voice |
| `tts_edge_voice` | `en-US-AvaNeural` | Edge TTS voice name |
| `kokoro_voice` | `af_sky` | Kokoro voice name |
| `kokoro_speed` | `1.0` | Kokoro speech speed |
| `kokoro_lang` | `en-us` | Kokoro language variant |
| `neutts_model` | `neuphonic/neutts-air` | NeuTTS model repo |
| `neutts_device` | `cpu` | NeuTTS compute device |
| `neutts_ref_audio` | `null` | Reference audio for voice cloning |
| `neutts_ref_text` | `null` | Reference transcript |
| `tts_api_key` | `null` | TTS API key (env fallback) |

## Architecture

```
helpers/providers/
  base.py           – Abstract SttProvider / TtsProvider classes
  stt_openai.py     – OpenAI Whisper STT
  stt_xai.py        – X.ai Grok STT
  stt_parakeet.py   – Local ONNX Parakeet STT
  tts_openai.py     – OpenAI TTS
  tts_edge.py       – Edge TTS
  tts_kokoro.py     – Kokoro ONNX TTS (local CPU)
  tts_neutts.py     – NeuTTS Air TTS (Neuphonic)

extensions/python/
  monologue_start/_10_transcribe_voice.py  – STT transcription
  process_chain_end/_40_tts_response.py     – TTS voice response
  job_loop/_20_telegram_commands.py          – Telegram slash commands
```

Each provider implements a simple interface:
- STT: `transcribe(file_path, language=None, keyterms=None) -> str`
- TTS: `synthesize(text, output_path) -> str`
