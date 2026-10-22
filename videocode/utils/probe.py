#!/usr/bin/env python3

from __future__ import annotations

#
# Reading a video file's own numbers — size and frame rate — before a scene
# is built around it.
#
# `Video` only learns them once the engine decodes it, which is too late for
# a scene that must size, crop or retime the clip at construction time. The
# answer comes from `ffprobe`, which ships with ffmpeg.
#

import subprocess

from videocode.ty import number


def probeVideo(path: str) -> tuple[number, number, number]:
    """
    `(width, height, fps)` of the first video stream of `path`.

    `fps` is the AVERAGE frame rate (`avg_frame_rate`, a fraction such as
    `60/1`), which is the right one for screen captures: they are variable
    rate, and the nominal rate would lie about how many frames there are.

    Raises `subprocess.CalledProcessError` if `ffprobe` cannot read the file,
    and `ValueError` if the stream has no usable rate.

        width, height, fps = probeVideo("game.mov")
    """
    out = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height,avg_frame_rate",
            "-of", "csv=p=0", path,
        ],
        capture_output=True, text=True, check=True,
    )
    width, height, rate = out.stdout.strip().split(",")[:3]
    num, _, den = rate.partition("/")
    if float(den or 1) == 0:
        raise ValueError(f"{path}: no frame rate in the video stream")
    return float(width), float(height), float(num) / float(den or 1)
