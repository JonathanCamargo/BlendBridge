#!/bin/bash
# Export BlendBridge addon as a .zip for Blender addon install (Linux/macOS)
cd "$(dirname "$0")"

# Clear stale __pycache__ from installed extension (Blender 4.x default path)
for BLENDER_VER in "$HOME/.config/blender"/*/; do
    EXT_DIR="${BLENDER_VER}extensions/user_default/blendbridge"
    ADDON_DIR="${BLENDER_VER}scripts/addons/addon"
    for DIR in "$EXT_DIR" "$ADDON_DIR"; do
        if [ -d "$DIR" ]; then
            find "$DIR" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
        fi
    done
done

python scripts/build_addon_zip.py --output /tmp
