# Documentation about ffmpeg

## Arguments

- `-i`
input file (can have many)

- `-filter_complex`
complex filter to apply on many inputs/outputs (filter;filter;...)
  - `concat` concatenate 2 video, one after the other
  - `overlay` place one video on top of another video at a certain position. W/H = main video width/height, w/h = overlay video width/height
  - `hstack` stack 2 video horizontally


- `-vf`
video filter to apply on one video stream
  - `scale` scale the video
  - `format` change the format (grayscale for example)

- `-af`
audio filter to apply on one audio stream
  - `volume` change the volume

- `-map`
maps a stream to the output file. e.g. the concat filters will have some output stream that you can redirect (map) into the output file.

## Loudness: `--loudness <LUFS>`

`video-code --file scene.py --generate out.mp4 --loudness -14` writes a file whose
integrated loudness is −14 LUFS. Spotify publishes −14 LUFS with a −1 dBTP peak,
Apple Podcasts −16 LKFS. YouTube, TikTok and Instagram publish no figure. The flag
is off by default, and without it the ffmpeg command is the same text as before.

It is ffmpeg's `loudnorm` in two passes:

1. Before the first frame, one audio-only ffmpeg run reads the scene's mix: the
   same inputs and filter as the render, the same `--from`/`--to` window, and the
   same clamp to the film's length. It ends in
   `loudnorm=I=<target>:TP=-1:LRA=11:print_format=json`, writes to `-f null -`,
   and its JSON report holds the measured values (`VC::Audio::Loudness`).
2. The render adds one stage after the mix:
   `loudnorm=I=<target>:TP=-1:LRA=<lra>:measured_I=…:measured_LRA=…:measured_TP=…:measured_thresh=…:offset=…:linear=true`,
   then `aresample=48000`, because `loudnorm` outputs 192 kHz. `<lra>` is the
   larger of 11 and the measured range, at most 50. `measured_LRA` is at least
   0.01: ffmpeg 9.0.2 uses dynamic mode for `measured_LRA=0.00`, and a short clip
   often measures 0.00 (a steady tone, and 8 s of real music, did).

One pass alone is not linear: with nothing measured, `loudnorm` falls back to
dynamic mode and rides the gain through the film. After the render, one line says
what happened, with the type that the render's `loudnorm` reports:

```
Loudness: -41.5 LUFS -> -14.0 LUFS target (linear)
```

`dynamic` is printed when ffmpeg used it. ffmpeg 9.0.2 used it for a gain that
would put the peak above −1 dBTP, and then the target can be missed: steady pink
noise at −40.7 LUFS, asked for −5, came out at −9.7 LUFS by `ebur128`. The same
noise asked for −20 was linear, at −20.5 (both measured).

The target is −70 to −5, the range `loudnorm` accepts. Another value, or
`--loudness` without `--generate`, is refused before the scene runs. With `--for`
and `--data`, each file is measured on its own. These render as before and print
the reason in one line: a scene with no sound, a GIF or an image, and a mix that
measures −70 LUFS or lower, where the gain has no bound.

Only the export is normalised. The editor preview, and its Export dialog, still
play and write the mix as it is.

Two meters can disagree. On a tone that steps up 6 dB, `loudnorm` read −41.5 LUFS
and `ebur128` read −42.2, so the file came out at −14.7 by `ebur128`. On a steady
tone or noise they agreed to 0.1 LU (measured, ffmpeg 9.0.2).

## Vocabulary
- `stream`
part of a video/image
  - `video`
  - `audio`
  - `subtitle`
  - `metadata`
