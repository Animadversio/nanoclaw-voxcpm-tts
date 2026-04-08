# nanoclaw-voxcpm-tts

Local text-to-speech for [NanoClaw](https://github.com/qwibitai/nanoclaw) using [VoxCPM2](https://github.com/OpenBMB/VoxCPM) — an open-source TTS model from OpenBMB. Your agent generates speech on-device and sends the audio file back to you via Discord.

**"Say hello world"** → agent generates a WAV → Discord delivers it as an audio attachment.

## Features

- Local generation — no cloud TTS API, no cost, no data leaving your machine
- ~1.5s generation on RTX 4070 SUPER (10 diffusion steps)
- Voice styling via natural-language descriptors: `(A calm narrator) ...`
- Voice cloning from a reference WAV
- 48kHz high-quality output
- Adds reusable `sendFile` IPC support to NanoClaw (useful for images, PDFs, etc. too)

## Requirements

- [NanoClaw](https://github.com/qwibitai/nanoclaw) with a Discord channel
- Python 3.10+ with PyTorch 2.5+ (CUDA GPU strongly recommended; CPU works but is slow)
- ~8GB disk for VoxCPM2 model weights (downloaded automatically on first use)

## Quick install

```bash
# 1. Clone this repo
git clone https://github.com/binxu/nanoclaw-voxcpm-tts
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
├── container/skills/voxcpm-tts/
│   └── SKILL.md                        # Runtime skill: teaches agent how to generate TTS
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
