---
name: add-voxcpm-tts
description: Add VoxCPM2 text-to-speech to NanoClaw. Installs the voxcpm Python package, adds file attachment support to the IPC/Discord layer, and registers a /tts container skill so the agent can speak on demand. GPU recommended (NVIDIA CUDA or Apple Silicon). Triggers on "add voxcpm", "add tts", "text to speech", "/add-voxcpm-tts".
---

# /add-voxcpm-tts — VoxCPM2 Text-to-Speech Setup

This skill adds local text-to-speech to NanoClaw using [VoxCPM2](https://github.com/OpenBMB/VoxCPM) — a high-quality open-source TTS model that runs on your GPU. After setup, you can say "say hello" or `/tts Hello world` and the agent will generate and send you an audio file.

## What this skill does

1. **Applies source changes** from `skill/voxcpm-tts` branch — adds `sendFile` support to the IPC layer and Discord channel, allowing the agent to send audio files (not just text)
2. **Installs voxcpm** Python package into your conda/Python environment
3. **Registers the container skill** so the agent knows how to generate TTS on demand

## Requirements

- NanoClaw running on Linux (or macOS with Metal)
- Python environment with PyTorch 2.5+ (CUDA recommended, CPU works but is slow)
- Conda environment named `research` OR you can configure a different Python path
- Discord channel (file upload uses Discord's file attachment API)
- ~8GB disk for VoxCPM2 model weights (downloaded automatically on first run)

## Step 1 — Merge the skill branch

```bash
cd /path/to/nanoclaw
git fetch origin skill/voxcpm-tts
git merge origin/skill/voxcpm-tts --no-edit
```

This adds:
- `sendFile(jid, filePath, caption?)` to the `Channel` interface (`src/types.ts`)
- Discord `sendFile` implementation using `AttachmentBuilder` (`src/channels/discord.ts`)
- IPC support for `file_path` field in message JSON (`src/ipc.ts`)
- Wiring in the orchestrator (`src/index.ts`)
- The `container/skills/voxcpm-tts/SKILL.md` runtime skill

## Step 2 — Build NanoClaw

```bash
npm run build
# or if there are pre-existing type errors, force emit:
./node_modules/.bin/tsc --noEmitOnError false
```

## Step 3 — Install voxcpm

Install into whichever Python environment your NanoClaw host uses. With conda:

```bash
# Replace with your actual Python path
/path/to/conda/envs/research/bin/pip install voxcpm
```

First install takes a few minutes (pulls funasr, gradio, modelscope, etc.).

Verify:
```bash
/path/to/conda/envs/research/bin/pip show voxcpm
```

## Step 4 — Update the container skill with your Python path

Edit `container/skills/voxcpm-tts/SKILL.md` and replace `/home/binxu/miniforge3/envs/research/bin/python` with the path to your Python binary:

```bash
which python  # or: conda run -n research which python
```

## Step 5 — Rebuild the agent container (if using Docker)

If your NanoClaw uses Docker containers (not local mode):
```bash
./container/build.sh
```

If running in local mode (Docker disabled), skip this step.

## Step 6 — Restart NanoClaw

```bash
# Linux
systemctl --user restart nanoclaw

# macOS
launchctl kickstart -k gui/$(id -u)/com.nanoclaw
```

## Step 7 — Test it

Send your agent: **"say hello, VoxCPM is working!"**

The agent should generate a WAV file and send it back as a Discord audio attachment within ~10–15 seconds on first run (model load), then ~2–3 seconds on subsequent calls.

## Troubleshooting

### "Failed to find C compiler" error
This is expected — the CLI (`voxcpm design`) requires gcc. The container skill uses the Python API directly with `torch._dynamo.config.suppress_errors = True`, which bypasses torch compilation and falls back to eager mode. No gcc needed.

### Model downloads on every session
The model is cached in `~/.cache/huggingface/hub/`. If `HF_HOME` is overridden in your environment, set it to a stable location.

### Audio not appearing in Discord
Check that `sendFile` is wired in `dist/ipc.js`:
```bash
grep "sendFile" /path/to/nanoclaw/dist/ipc.js
```
If missing, the build didn't include the skill branch changes — re-run Step 2.

### Slow generation
Increase `inference_timesteps` for quality, decrease for speed. 10 steps is fast (~1.5s on 4070 SUPER); 50 steps is high quality (~8s).

## Usage after setup

Once installed, just talk naturally:

- **"Say hello world"** — generates speech with default voice
- **"Read this aloud: [text]"** — same
- **"/tts (A calm narrator) Good evening."** — uses voice styling
- **"Clone this voice and say X"** — provide a reference WAV for voice cloning

The agent uses the `voxcpm-tts` container skill automatically when it detects a TTS request.
