#!/usr/bin/env python3
"""
Audiobook generator for NanoClaw + VoxCPM2.

Reads a .md or .epub file, splits into chapters, generates speech for each,
converts to MP3, and delivers to a Discord channel via IPC as chapters finish.

Usage:
    python audiobook_gen.py <file.md|file.epub> \\
        --jid dc:1234567890 \\
        --ipc /path/to/ipc/messages \\
        [--voice "calm British narrator"] \\
        [--steps 20] \\
        [--bitrate 64k] \\
        [--outdir /tmp/audiobook] \\
        [--start 0]
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

# Ensure conda env binaries (ffmpeg) are on PATH
_CONDA_BIN = '/home/binxu/miniforge3/envs/research/bin'
if _CONDA_BIN not in os.environ.get('PATH', ''):
    os.environ['PATH'] = _CONDA_BIN + ':' + os.environ.get('PATH', '')

# ── Text extraction ────────────────────────────────────────────────────────────

def extract_chapters_md(filepath: Path) -> list[dict]:
    """Split markdown into sections by # or ## headings."""
    text = filepath.read_text(encoding='utf-8')
    # Split on lines that start with 1-2 # signs
    parts = re.split(r'(?=^#{1,2} )', text, flags=re.MULTILINE)
    chapters = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        lines = part.split('\n')
        heading = re.sub(r'^#{1,2}\s*', '', lines[0]).strip()
        body = '\n'.join(lines[1:]).strip()
        if not body:
            body = part  # no heading found, treat whole block as body
        chapters.append({'title': heading or 'Section', 'text': body})
    # If no headings found, treat the whole file as one chapter
    if len(chapters) <= 1 and chapters:
        chapters[0]['title'] = filepath.stem
    return chapters


def extract_chapters_epub(filepath: Path) -> list[dict]:
    """Extract chapters from EPUB using ebooklib."""
    import ebooklib
    from ebooklib import epub
    from html.parser import HTMLParser

    class _Extractor(HTMLParser):
        def __init__(self):
            super().__init__()
            self.chunks, self._buf, self._skip = [], [], False
        def handle_starttag(self, tag, attrs):
            if tag in ('script', 'style'):
                self._skip = True
            elif tag in ('p', 'br', 'h1', 'h2', 'h3', 'h4', 'li'):
                if self._buf:
                    self.chunks.append(''.join(self._buf).strip())
                    self._buf = []
        def handle_endtag(self, tag):
            if tag in ('script', 'style'):
                self._skip = False
        def handle_data(self, data):
            if not self._skip:
                self._buf.append(data)
        def get_text(self):
            if self._buf:
                self.chunks.append(''.join(self._buf).strip())
            return ' '.join(c for c in self.chunks if c)

    book = epub.read_epub(str(filepath))
    chapters = []
    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        parser = _Extractor()
        parser.feed(item.get_content().decode('utf-8', errors='ignore'))
        text = parser.get_text().strip()
        if len(text) < 150:
            continue  # skip nav/toc/cover pages
        # Try to pull a title from epub metadata or filename
        name = item.get_name() or ''
        title = re.sub(r'[_\-/]', ' ', Path(name).stem).strip().title()
        chapters.append({'title': title or 'Chapter', 'text': text})
    return chapters


# ── Language detection ────────────────────────────────────────────────────────

# CJK unicode ranges
_CJK_RE = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]')
_JAPANESE_RE = re.compile(r'[\u3040-\u30ff]')
_KOREAN_RE = re.compile(r'[\uac00-\ud7af\u1100-\u11ff]')
_ARABIC_RE = re.compile(r'[\u0600-\u06ff]')
_CYRILLIC_RE = re.compile(r'[\u0400-\u04ff]')

def detect_language(text: str) -> str:
    """Return a rough language code for the dominant script."""
    sample = text[:500]
    if len(_JAPANESE_RE.findall(sample)) > 5:
        return 'ja'
    if len(_KOREAN_RE.findall(sample)) > 5:
        return 'ko'
    if len(_CJK_RE.findall(sample)) > 10:
        return 'zh'
    if len(_ARABIC_RE.findall(sample)) > 5:
        return 'ar'
    if len(_CYRILLIC_RE.findall(sample)) > 10:
        return 'ru'
    return 'en'

# Default voice styles per language (used when user doesn't specify --voice)
DEFAULT_VOICES = {
    'zh': '平静温和的女声播音员',          # calm warm female broadcaster
    'en': 'calm, clear narrator',
    'ja': '落ち着いた女性のナレーター',       # calm female narrator
    'ko': '차분하고 따뜻한 여성 나레이터',    # calm warm female narrator
    'ar': 'calm Arabic narrator',
    'ru': 'calm Russian narrator',
}

def get_default_voice(lang: str) -> str:
    return DEFAULT_VOICES.get(lang, DEFAULT_VOICES['en'])


# ── Text normalization ─────────────────────────────────────────────────────────

def normalize_for_tts(text: str) -> str:
    """Strip markup and normalize text for clean TTS output."""
    # Code blocks
    text = re.sub(r'```[\s\S]*?```', ' [code block] ', text)
    text = re.sub(r'`([^`]+)`', r'\1', text)
    # Markdown links and images
    text = re.sub(r'!\[[^\]]*\]\([^\)]+\)', '', text)
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    # HTML tags
    text = re.sub(r'<[^>]+>', ' ', text)
    # Bold / italic markers
    text = re.sub(r'\*{1,3}([^\*\n]+)\*{1,3}', r'\1', text)
    text = re.sub(r'_{1,3}([^_\n]+)_{1,3}', r'\1', text)
    # Heading markers
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    # Horizontal rules
    text = re.sub(r'^[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)
    # Footnote-style references [1], [^1]
    text = re.sub(r'\[\^?\d+\]', '', text)
    # Collapse whitespace
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def split_into_segments(text: str, max_chars: int = 1800) -> list[str]:
    """
    Split text into segments of at most max_chars.
    Tries to break at sentence boundaries.
    """
    if len(text) <= max_chars:
        return [text]

    segments = []
    # Split on sentence-ending punctuation followed by whitespace
    sentences = re.split(r'(?<=[.!?])\s+', text)
    buf = ''
    for sent in sentences:
        if len(buf) + len(sent) + 1 > max_chars:
            if buf:
                segments.append(buf.strip())
            buf = sent
        else:
            buf = (buf + ' ' + sent).strip() if buf else sent
    if buf:
        segments.append(buf.strip())
    return segments


# ── Audio generation ───────────────────────────────────────────────────────────

def load_model():
    """Load VoxCPM2 model (call once; reuse across chapters)."""
    import torch._dynamo
    torch._dynamo.config.suppress_errors = True
    from voxcpm import VoxCPM
    print('[audiobook] Loading VoxCPM2 model...', flush=True)
    model = VoxCPM.from_pretrained('openbmb/VoxCPM2', load_denoiser=False)
    print('[audiobook] Model ready.', flush=True)
    return model


def generate_segment(model, text: str, voice_style: str, steps: int) -> tuple:
    """Generate a single audio segment. Returns (wav_array, sample_rate)."""
    prompt = f'({voice_style}) {text}' if voice_style else text
    wav = model.generate(text=prompt, cfg_value=2.0, inference_timesteps=steps)
    return wav, model.tts_model.sample_rate


def generate_chapter_audio(model, text: str, voice_style: str, steps: int,
                            out_wav: Path) -> None:
    """Generate audio for a full chapter (splits long text, concatenates)."""
    import numpy as np
    import soundfile as sf

    segments = split_into_segments(text, max_chars=1800)
    print(f'  {len(segments)} segment(s)', flush=True)

    parts = []
    sample_rate = None
    for j, seg in enumerate(segments):
        print(f'  segment {j+1}/{len(segments)} ({len(seg)} chars)...', flush=True)
        wav, sr = generate_segment(model, seg, voice_style, steps)
        parts.append(wav)
        sample_rate = sr

    combined = np.concatenate(parts) if len(parts) > 1 else parts[0]
    sf.write(str(out_wav), combined, sample_rate)


def wav_to_mp3(wav_path: Path, mp3_path: Path, bitrate: str = '64k') -> None:
    """Convert WAV → MP3 via pydub (uses ffmpeg under the hood)."""
    from pydub import AudioSegment
    audio = AudioSegment.from_wav(str(wav_path))
    audio.export(str(mp3_path), format='mp3', bitrate=bitrate)


# ── IPC delivery ───────────────────────────────────────────────────────────────

def _write_ipc(ipc_dir: str, msg: dict) -> None:
    fname = Path(ipc_dir) / f'audiobook-{int(time.time() * 1000)}.json'
    fname.write_text(json.dumps(msg))
    time.sleep(0.3)  # small delay so IPC watcher processes in order


def ipc_send_file(ipc_dir: str, jid: str, file_path: str, caption: str) -> None:
    _write_ipc(ipc_dir, {
        'type': 'message',
        'chatJid': jid,
        'file_path': file_path,
        'text': caption,
    })


def ipc_send_text(ipc_dir: str, jid: str, text: str) -> None:
    _write_ipc(ipc_dir, {
        'type': 'message',
        'chatJid': jid,
        'text': text,
    })


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Generate audiobook from .md or .epub')
    parser.add_argument('input', help='Path to .md or .epub file')
    parser.add_argument('--jid', required=True, help='Discord channel JID (dc:xxxxx)')
    parser.add_argument('--ipc', required=True, help='Path to IPC messages directory')
    parser.add_argument('--voice', default='', help='Voice style e.g. "calm British narrator"')
    parser.add_argument('--steps', type=int, default=20, help='Diffusion steps (10=fast, 50=quality)')
    parser.add_argument('--bitrate', default='64k', help='MP3 bitrate')
    parser.add_argument('--outdir', default='/tmp/audiobook', help='Output directory for MP3s')
    parser.add_argument('--start', type=int, default=0, help='Resume from chapter N (0-indexed)')
    args = parser.parse_args()

    input_path = Path(args.input)
    out_dir = Path(args.outdir) / input_path.stem
    out_dir.mkdir(parents=True, exist_ok=True)

    ext = input_path.suffix.lower()
    if ext == '.md':
        chapters = extract_chapters_md(input_path)
    elif ext in ('.epub',):
        chapters = extract_chapters_epub(input_path)
    else:
        print(f'Unsupported format: {ext}', file=sys.stderr)
        sys.exit(1)

    # Filter very short chapters
    chapters = [c for c in chapters if len(normalize_for_tts(c['text'])) >= 80]
    total = len(chapters)

    print(f'[audiobook] {input_path.name}: {total} chapters', flush=True)

    # Auto-detect language from first substantial chapter
    sample_text = next((normalize_for_tts(c['text']) for c in chapters if len(c['text']) > 100), '')
    lang = detect_language(sample_text)

    # Use user-specified voice or language default
    voice = args.voice if args.voice else get_default_voice(lang)

    lang_label = {'zh': '🇨🇳 Chinese', 'en': '🇬🇧 English', 'ja': '🇯🇵 Japanese',
                  'ko': '🇰🇷 Korean', 'ar': '🇸🇦 Arabic', 'ru': '🇷🇺 Russian'}.get(lang, lang)
    voice_label = f' | {lang_label} | voice: "{voice}"'
    ipc_send_text(args.ipc, args.jid,
        f'**{input_path.stem}** — {total} chapters detected. Generating audio...{voice_label}')

    # Load model once
    os.environ['TORCH_COMPILE_DISABLE'] = '1'
    model = load_model()

    errors = 0
    for i, chapter in enumerate(chapters):
        if i < args.start:
            continue

        title = chapter['title']
        text = normalize_for_tts(chapter['text'])
        print(f'\n[{i+1}/{total}] {title} ({len(text)} chars)', flush=True)

        wav_path = out_dir / f'ch{i+1:03d}.wav'
        safe_title = re.sub(r'[^\w\s-]', '', title)[:40]
        mp3_path = out_dir / f'ch{i+1:03d} - {safe_title}.mp3'

        try:
            generate_chapter_audio(model, text, voice, args.steps, wav_path)
            wav_to_mp3(wav_path, mp3_path, args.bitrate)
            wav_path.unlink(missing_ok=True)

            size_mb = mp3_path.stat().st_size / 1024 / 1024
            duration_est = size_mb * 8 / (int(args.bitrate.replace('k', '')) / 1000) / 60
            ipc_send_file(args.ipc, args.jid, str(mp3_path),
                f'**Ch. {i+1}/{total}:** {title} (~{duration_est:.0f} min, {size_mb:.1f} MB)')

        except Exception as e:
            errors += 1
            msg = str(e)[-300:]
            print(f'ERROR ch{i+1}: {msg}', file=sys.stderr)
            ipc_send_text(args.ipc, args.jid, f'⚠️ Chapter {i+1} failed: {msg}')

    status = '✅ Done!' if errors == 0 else f'⚠️ Done with {errors} error(s).'
    ipc_send_text(args.ipc, args.jid,
        f'{status} **{input_path.stem}** — {total - errors}/{total} chapters delivered.')


if __name__ == '__main__':
    main()
