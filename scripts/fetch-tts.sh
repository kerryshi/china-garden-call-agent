#!/usr/bin/env bash
# One-time fetch of the Kokoro-82M model files (Apache-2.0) for offline TTS.
# ~340MB total. Re-run is a no-op if the files already exist.
set -euo pipefail

DIR="${CG_TTS_DIR:-$HOME/.cache/china-garden-tts}"
BASE="https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
mkdir -p "$DIR"

for f in kokoro-v1.0.onnx voices-v1.0.bin; do
  if [ -s "$DIR/$f" ]; then
    echo "already have $f"
  else
    echo "fetching $f ..."
    curl -L --fail -o "$DIR/$f.part" "$BASE/$f"
    mv "$DIR/$f.part" "$DIR/$f"
  fi
done
echo "TTS model ready in $DIR"
