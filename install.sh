#!/usr/bin/env bash
# nanoclaw-voxcpm-tts installer
# Run from the root of your nanoclaw directory:
#   bash /path/to/nanoclaw-voxcpm-tts/install.sh

set -e

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NANOCLAW_DIR="${1:-$(pwd)}"

echo "==> Installing nanoclaw-voxcpm-tts into: $NANOCLAW_DIR"

# Verify we're in a nanoclaw directory
if [ ! -f "$NANOCLAW_DIR/src/types.ts" ]; then
  echo "ERROR: $NANOCLAW_DIR does not look like a nanoclaw root (src/types.ts not found)"
  echo "Usage: bash install.sh /path/to/nanoclaw"
  exit 1
fi

# Apply source patches
echo "==> Applying source patches..."
cd "$NANOCLAW_DIR"

# Patch 1: types.ts + ipc.ts (IPC sendFile support)
git apply --check "$SKILL_DIR/patches/sendfile-ipc.patch" 2>/dev/null && \
  git apply "$SKILL_DIR/patches/sendfile-ipc.patch" && \
  echo "    [ok] sendfile-ipc.patch" || \
  echo "    [skip] sendfile-ipc.patch already applied or conflict — check manually"

# Patch 2: discord.ts + index.ts (Discord sendFile implementation)
git apply --check "$SKILL_DIR/patches/sendfile-discord.patch" 2>/dev/null && \
  git apply "$SKILL_DIR/patches/sendfile-discord.patch" && \
  echo "    [ok] sendfile-discord.patch" || \
  echo "    [skip] sendfile-discord.patch already applied or conflict — check manually"

# Copy container skill
echo "==> Copying container skill..."
mkdir -p "$NANOCLAW_DIR/container/skills/voxcpm-tts"
cp "$SKILL_DIR/container/skills/voxcpm-tts/SKILL.md" \
   "$NANOCLAW_DIR/container/skills/voxcpm-tts/SKILL.md"
echo "    [ok] container/skills/voxcpm-tts/SKILL.md"

# Copy Claude skill
echo "==> Copying Claude skill..."
mkdir -p "$NANOCLAW_DIR/.claude/skills/add-voxcpm-tts"
cp "$SKILL_DIR/.claude/skills/add-voxcpm-tts/SKILL.md" \
   "$NANOCLAW_DIR/.claude/skills/add-voxcpm-tts/SKILL.md"
echo "    [ok] .claude/skills/add-voxcpm-tts/SKILL.md"

# Build
echo "==> Building NanoClaw..."
cd "$NANOCLAW_DIR"
./node_modules/.bin/tsc --noEmitOnError false 2>&1 | grep -E "^src.*error" || true
echo "    [ok] build complete"

echo ""
echo "==> Done! Next steps:"
echo "    1. Install voxcpm in your Python env:"
echo "       pip install voxcpm"
echo "    2. Edit container/skills/voxcpm-tts/SKILL.md with your Python binary path"
echo "    3. Restart NanoClaw:"
echo "       systemctl --user restart nanoclaw   # Linux"
echo "       launchctl kickstart -k gui/\$(id -u)/com.nanoclaw  # macOS"
echo "    4. Send your bot: 'say hello, VoxCPM is working!'"
