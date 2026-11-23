#!/bin/bash

set -e

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <video_file>" >&2
    exit 1
fi

VIDEO="$1"

# Allow filenames relative to ~/videos/
if [ ! -f "$VIDEO" ]; then
    VIDEO="$HOME/videos/$VIDEO"
fi

if [ ! -f "$VIDEO" ]; then
    echo "Error: Video not found: $1" >&2
    exit 1
fi

exec cvlc \
    --vout=drm_vout \
    --drm-vout-no-modeset \
    --aout=alsa \
    --alsa-audio-device=hdmi:CARD=vc4hdmi,DEV=0 \
    --fullscreen \
    "$VIDEO"
