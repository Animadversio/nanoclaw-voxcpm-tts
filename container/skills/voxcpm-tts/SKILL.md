---
name: voxcpm-tts
description: Generate speech from text using VoxCPM2 and send the audio file to the user. Use when the user asks you to "say", "speak", "read aloud", "generate speech", or "/tts".
---

# VoxCPM TTS — Text-to-Speech Skill

Generate high-quality speech from text using the VoxCPM2 model running locally on the host GPU, then deliver the audio file to the user via Discord.

## Prerequisites

VoxCPM must be installed in the `research` conda environment:
```bash
/home/binxu/miniforge3/envs/research/bin/pip show voxcpm
```

If not installed, tell the user to run `/add-voxcpm-tts` first.

## How to generate and send speech

### Step 1 — Generate the audio

Run this Python script via Bash. Adjust `TEXT_TO_SPEAK` to the user's text.

```bash
TORCH_COMPILE_DISABLE=1 /home/binxu/miniforge3/envs/research/bin/python -c "
import torch._dynamo
torch._dynamo.config.suppress_errors = True

from voxcpm import VoxCPM
import soundfile as sf
import time, os

text = '''TEXT_TO_SPEAK'''
output_path = f'/tmp/voxcpm-{int(time.time())}.wav'

model = VoxCPM.from_pretrained('openbmb/VoxCPM2', load_denoiser=False)
wav = model.generate(
    text=text,
    cfg_value=2.0,
    inference_timesteps=10,
)
sf.write(output_path, wav, model.tts_model.sample_rate)
print(output_path)
" 2>/dev/null
```

The script prints the output file path on the last line. Capture it.

### Step 2 — Send the audio file via IPC

Write an IPC message to deliver the file to the user. Find the group IPC directory from the environment or use `/workspace/ipc/messages/`:

```bash
import json, time, os

ipc_dir = '/workspace/ipc/messages'
msg = {
    "type": "message",
    "chatJid": "CHAT_JID",   # from CLAUDE.md context or chat_jid env
    "file_path": "OUTPUT_PATH_FROM_STEP_1",
    "text": "Here's your audio!"
}
fname = f'{ipc_dir}/tts-{int(time.time())}.json'
with open(fname, 'w') as f:
    json.dump(msg, f)
```

Or as a one-liner bash:
```bash
echo '{"type":"message","chatJid":"CHAT_JID","file_path":"OUTPUT_PATH","text":"Here is your audio!"}' \
  > /workspace/ipc/messages/tts-$(date +%s).json
```

The chatJid is in the conversation context (e.g. `dc:1491312252140130324`). It is shown in the CLAUDE.md header that was injected when the session started, or you can read it from:
```bash
cat /workspace/ipc/current_tasks.json | python3 -c "import json,sys; print(json.load(sys.stdin))" 2>/dev/null
```

### Step 3 — Confirm to the user

Tell the user the audio is on its way and mention the voice style or duration if available.

## Voice styling (optional)

VoxCPM2 supports natural-language voice descriptors in parentheses at the start of the text:

```
(A calm, deep male narrator) The quick brown fox...
(A cheerful young woman) Hello there!
(An excited sports commentator) And he scores!
```

If the user doesn't specify a voice, use the default (no descriptor).

## Voice cloning (optional)

If the user provides a reference audio file:
```python
wav = model.generate(
    text="Text to speak.",
    reference_wav_path="/path/to/voice_sample.wav",
    cfg_value=2.0,
    inference_timesteps=10,
)
```

## Performance notes

- First run loads the model (~10s). Subsequent runs are faster.
- ~10 steps ≈ 1.5s generation on RTX 4070 SUPER
- Output: 48kHz mono WAV
- More steps = higher quality but slower (10 is fast, 50 is high quality)
