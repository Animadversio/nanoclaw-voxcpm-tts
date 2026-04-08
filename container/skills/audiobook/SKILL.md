---
name: audiobook
description: Convert a book or document (.md or .epub) to an audiobook using VoxCPM2. Generates MP3 audio per chapter and delivers them to the user as they finish. Use when the user sends a document and asks to "read it", "make an audiobook", "convert to audio", or "/audiobook".
---

# /audiobook — Document to Audiobook

Converts `.md` or `.epub` files into speech using VoxCPM2, delivering one MP3 per chapter as it's generated (so the user can start listening immediately).

## How to use this skill

### 1. Identify the input file

The user will either:
- Attach a file to their Discord message — look for `[File: name.md]` or `[File: name.epub]` in the conversation. The file is downloaded to `/workspace/group/downloads/` or a temp path.
- Give you a local path on the host.

If the file is a Discord attachment described as `[File: foo.epub]` but not yet saved locally, ask the user to re-send it or check `/workspace/group/downloads/`.

### 2. Parse any options from the user's message

| Option | Default | Example |
|---|---|---|
| Voice style | *(default VoxCPM voice)* | "calm British male narrator" |
| Quality | 20 steps | "high quality" → use 40 steps |
| Speed | 20 steps | "fast" → use 10 steps |
| Start chapter | 0 | "start from chapter 3" → --start 2 |

### 3. Run the audiobook generator

```bash
TORCH_COMPILE_DISABLE=1 /home/binxu/miniforge3/envs/research/bin/python \
  /home/binxu/nanoclaw/scripts/audiobook_gen.py \
  "/path/to/book.epub" \
  --jid "dc:CHANNEL_ID" \
  --ipc "/workspace/ipc/messages" \
  --voice "calm British narrator" \
  --steps 20 \
  --bitrate 64k \
  --outdir "/tmp/audiobook"
```

Replace:
- `/path/to/book.epub` — actual file path
- `dc:CHANNEL_ID` — from the session context (e.g. `dc:1491312252140130324`)
- `--voice` — from user's request, or omit for default voice

The script sends progress messages and MP3 files to the user automatically as each chapter completes.

### 4. Monitor output

The script prints `[N/total] Chapter title` for each chapter. If it errors on a chapter, it reports to the user and continues. You don't need to intervene unless all chapters fail.

### 5. Confirm to the user

After starting the script (it runs in the foreground), tell the user:
- How many chapters were found
- Estimated voice style
- That chapters will arrive as they're generated

## Voice style examples

VoxCPM2 accepts natural-language voice descriptors:

| Request | Style prompt |
|---|---|
| "calm narrator" | `calm, measured narrator` |
| "British female" | `warm British female narrator` |
| "energetic" | `enthusiastic, energetic narrator` |
| "bedtime story" | `soft, gentle storyteller, slow pace` |
| *(none specified)* | omit `--voice` entirely |

## Supported formats

| Format | Chapter detection |
|---|---|
| `.md` | `#` and `##` headings |
| `.epub` | Native EPUB chapter structure |

PDF is not supported — ask the user to convert to EPUB or Markdown first.

## Language support

VoxCPM2 supports **30 languages** with no language tag required — just feed it the native text. The script auto-detects the dominant language and picks an appropriate default voice:

| Language | Default voice style |
|---|---|
| English | `calm, clear narrator` |
| Chinese 中文 | `平静温和的女声播音员` (+ dialects: Cantonese, Sichuan, etc.) |
| Japanese 日本語 | `落ち着いた女性のナレーター` |
| Korean 한국어 | `차분하고 따뜻한 여성 나레이터` |
| Arabic / Russian / others | `calm [language] narrator` |

The user can always override: `--voice "活泼的男声"` for a lively male Chinese voice, for example.

## File size notes

At 64kbps MP3: ~30 min audio ≈ 14 MB (within Discord's 25 MB limit).
Very long chapters are automatically split into ≤1800-character segments and concatenated before delivery.

## Resuming interrupted generation

If generation was interrupted, re-run with `--start N` where N is the last completed chapter index (0-based):

```bash
# Resume from chapter 5 (0-indexed = 4)
... --start 4
```

## Common issues

**"Unsupported format"** — Only `.md` and `.epub` are supported. Ask user to convert.

**Chapter too short / skipped** — Chapters under 80 characters are skipped (usually TOC entries or blank pages).

**Model not found** — VoxCPM must be installed: `/home/binxu/miniforge3/envs/research/bin/pip install voxcpm`
