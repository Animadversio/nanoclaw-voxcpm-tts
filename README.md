# nanoclaw-voxcpm-tts

Local text-to-speech for [NanoClaw](https://github.com/qwibitai/nanoclaw) using [VoxCPM2](https://github.com/OpenBMB/VoxCPM) — an open-source TTS model from OpenBMB. Your agent generates speech on-device and sends the audio file back to you via Discord.

**"Say hello world"** → agent generates a WAV → Discord delivers it as an audio attachment.

**Send a book** → agent converts it to a full audiobook, delivering chapters as they finish.

## Features

- Local generation — no cloud TTS API, no cost, no data leaving your machine
- ~1.5s generation on RTX 4070 SUPER (10 diffusion steps)
- **30-language support** — Chinese (+ dialects), English, Japanese, Korean, French, etc. Auto-detected
- Voice styling via natural-language descriptors: `(A calm narrator) ...`
- Voice cloning from a reference WAV
- **Audiobook mode** — EPUB and Markdown → per-chapter MP3s, delivered as they finish
- **YouTube upload** — auto-publishes chapters to an unlisted YouTube playlist
- 48kHz high-quality output
- Adds reusable `sendFile` IPC support to NanoClaw (useful for images, PDFs, etc. too)

## Requirements

- [NanoClaw](https://github.com/qwibitai/nanoclaw) with a Discord channel
- Python 3.10+ with PyTorch 2.5+ (CUDA GPU strongly recommended; CPU works but is slow)
- ~8GB disk for VoxCPM2 model weights (downloaded automatically on first use)

## Quick install

```bash
# 1. Clone this repo
git clone https://github.com/Animadversio/nanoclaw-voxcpm-tts
cd nanoclaw-voxcpm-tts

# 2. Run the installer (point it at your nanoclaw directory)
bash install.sh /path/to/nanoclaw

# 3. Install the voxcpm Python package
pip install voxcpm
# or with conda:
/path/to/conda/envs/myenv/bin/pip install voxcpm

# 4. Edit the container skill with your Python path
#    Open: /path/to/nanoclaw/container/skills/voxcpm-tts/SKILL.md
#    Replace the Python binary path on lines that invoke Python

# 5. Restart NanoClaw
systemctl --user restart nanoclaw       # Linux
launchctl kickstart -k gui/$(id -u)/com.nanoclaw  # macOS
```

---

## Audiobook workflow

Send your agent an EPUB or Markdown file and ask it to make an audiobook. The agent will:

1. Extract chapters (EPUB native structure, or Markdown `#`/`##` headings)
2. Auto-detect language and pick a matching default voice
3. Generate MP3 audio per chapter (segments kept ≤400 chars to stay within the model's KV cache)
4. Deliver each chapter immediately when done — you can start listening before the book finishes

### Example conversations

```
You: 把这本书做成有声书，平静温和的女声
    [File: book.epub]

Agent: 📖 *book* — 31 chapters detected. Language: zh. Voice: 平静温和的女声播音员. Starting...
       📖 Ch.1/31: 第一章 (6.0 MB)   ← arrives ~10 min later
       📖 Ch.2/31: 第二章 (16 MB)
       ...
```

```
You: /audiobook [File: paper.md]  (use a calm British narrator)

Agent: 📖 *paper* — 8 sections detected. Language: en. Voice: calm British narrator. Starting...
```

### Delivery options

| Method | How it works | Best for |
|--------|-------------|----------|
| **Discord attachments** | Each MP3 sent directly in the chat | Quick access, no setup |
| **Web player** | Python HTTP server + `localhost.run` SSH tunnel → shareable URL | Listening on phone/browser |
| **YouTube playlist** | Chapters auto-uploaded as unlisted videos | Permanent, phone YouTube app |

#### Setting up YouTube upload

1. Enable the [YouTube Data API v3](https://console.cloud.google.com/apis/library/youtube.googleapis.com) in Google Cloud Console
2. Create an OAuth 2.0 "Desktop app" client → download the JSON
3. Save to `/home/user/.config/nanoclaw/youtube_client_secret.json`
4. Run the auth flow once:
   ```bash
   python tools/youtube_upload.py --auth
   ```
   Open the printed URL in your browser, authorize, paste the redirect URL back.
5. Tell your agent: *"upload audiobook chapters to YouTube"* — it creates a playlist and auto-uploads as chapters finish.

### Technical notes

**KV cache limit**: VoxCPM2 has a hard 8192-token context window. Chinese text maps ~1 char → 1 token. Chapters are split into ≤400-char segments at sentence boundaries (handles `。！？.!?` and other punctuation), then concatenated with pydub.

**Voice consistency**: The `(voice description)` prefix is included in every segment, not just the first, giving consistent voice across the whole chapter.

**Resuming**: If generation is interrupted, re-run with `--start N` (0-indexed chapter number):
```bash
python scripts/audiobook_gen.py book.epub --jid dc:xxx --ipc /path/to/ipc/messages --start 4
```

**Audio quality vs. speed**:
| Steps | Quality | Time per segment |
|-------|---------|-----------------|
| 10 | Good | ~15s |
| 20 | Better | ~25s |
| 40 | Best | ~50s |

---

## Or let Claude do it

If your NanoClaw has Claude Code access, just say:

> Clone https://github.com/binxu/nanoclaw-voxcpm-tts and integrate it

Claude will clone the repo, run the installer, update the Python path, and restart the service.

Alternatively, the `/add-voxcpm-tts` skill is included — Claude reads `.claude/skills/add-voxcpm-tts/SKILL.md` and walks through the setup interactively.

## Usage after install

Talk to your agent naturally:

| You say | What happens |
|---|---|
| `say hello world` | Generates speech, sends WAV |
| `read this aloud: [text]` | Same |
| `(A cheerful woman) Good morning!` | Voice-styled speech |
| `/tts [text]` | Explicit TTS command |

## What's in this repo

```
nanoclaw-voxcpm-tts/
├── README.md
├── install.sh                          # One-command installer
├── patches/
│   ├── sendfile-ipc.patch              # Adds file_path field to IPC messages
│   └── sendfile-discord.patch          # Adds sendFile() to Discord channel
├── scripts/
│   └── audiobook_gen.py               # Audiobook pipeline: EPUB/MD → MP3 chapters
├── tools/
│   ├── audiobook_server.py            # HTTP server + RSS feed for web player
│   └── youtube_upload.py             # YouTube Data API uploader (MP3 → unlisted video)
├── container/skills/
│   ├── voxcpm-tts/SKILL.md            # Runtime skill: agent generates TTS on demand
│   └── audiobook/SKILL.md             # Runtime skill: agent converts books to audiobooks
└── .claude/skills/add-voxcpm-tts/
    └── SKILL.md                        # Setup skill: guides through installation
```

### Source changes (via patches)

The installer applies two small patches to NanoClaw source:

- **`sendfile-ipc.patch`** — IPC message handler now accepts `file_path` alongside `text`. Any skill can drop a JSON file like `{"type":"message","chatJid":"dc:...","file_path":"/tmp/audio.wav","text":"caption"}` to deliver files.
- **`sendfile-discord.patch`** — Discord channel gains a `sendFile()` method using `discord.js` `AttachmentBuilder`. Wired into the orchestrator's IPC deps.

These changes are channel-agnostic — `sendFile` is an optional method on the `Channel` interface, so other channels (Telegram, Slack, WhatsApp) can implement it independently without breaking anything.

## Troubleshooting

**"Failed to find C compiler"** — Expected. The CLI uses torch.compile which needs gcc. The skill uses the Python API with `torch._dynamo.config.suppress_errors = True`, bypassing compilation. No gcc needed.

**Audio not showing up in Discord** — Check that the patch applied: `grep sendFile /path/to/nanoclaw/dist/ipc.js`. If missing, re-run the build step in `install.sh`.

**Slow generation** — Adjust `inference_timesteps` in the skill. 10 = fast (~1.5s), 50 = high quality (~8s).

**Model re-downloading** — The model caches in `~/.cache/huggingface/hub/`. If `HF_HOME` is set elsewhere in your environment, set it to a persistent path.

## License

MIT
