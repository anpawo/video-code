"""
The two sounds of a vote, drawn rather than recorded: the pop a label lands on, and the rising
trill that closes a wave of seats.

Their shapes were measured on the reference Reel (videos/politics/ref, kept out of git): the pop
is a tone that falls from about 750 Hz to 320 Hz in 50 ms and is gone in 120; the trill is a tick
every 20 ms, near 2.4 kHz, climbing about 16 % from first to last and getting louder. Written out
as plain waves they carry no hiss, no voice and nobody else's recording, and they end on a decay
instead of a cut.

    Sound(pop()); Sound(fill(0.3), start=0.4)

Each call returns the path of a wav under videos/politics/media/sfx, written on first use. Nothing
random goes into them: the same call is the same file, byte for byte.
"""

import io
import math
import struct
import wave
from pathlib import Path

RATE = 44100
MEDIA = Path(__file__).parent / "media" / "sfx"


def _write(name: str, samples: list[float]) -> str:
    held = io.BytesIO()
    with wave.open(held, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(RATE)
        out.writeframes(b"".join(struct.pack("<h", round(max(-1.0, min(1.0, s)) * 32767)) for s in samples))
    # Written only when it differs: a file rewritten at every run would wake whatever watches
    # the folder, and one kept by name alone would outlive a change to the sound.
    path = MEDIA / name
    if not path.exists() or path.read_bytes() != held.getvalue():
        MEDIA.mkdir(parents=True, exist_ok=True)
        path.write_bytes(held.getvalue())
    return str(path)


def _fadeOut(samples: list[float], seconds: float) -> list[float]:
    """A raised-cosine close over the last `seconds`, so the file ends on silence, not on a step."""
    n = min(len(samples), int(seconds * RATE))
    for i in range(n):
        samples[len(samples) - n + i] *= math.cos(math.pi / 2 * i / n) ** 2
    return samples


def pop(volume: float = 0.5) -> str:
    """The label's pop: 750 Hz falling to 320 Hz, 3 ms of attack, a 30 ms decay."""
    phase, out = 0.0, []
    for i in range(int(0.16 * RATE)):
        t = i / RATE
        phase += 2 * math.pi * (320 + 430 * math.exp(-t / 0.009)) / RATE
        loud = min(1.0, t / 0.003) * math.exp(-t / 0.030)
        out.append(volume * loud * (math.sin(phase) + 0.15 * math.sin(2 * phase)))
    return _write(f"pop-{volume:.2f}.wav", _fadeOut(out, 0.05))


def fill(seconds: float = 0.3, volume: float = 0.3) -> str:
    """
    The trill that closes a wave of seats: one tick every 20 ms for `seconds`, from 2350 Hz up
    16 %, each a little louder than the last, the final one left to ring.
    """
    ticks = max(2, round(seconds / 0.02))
    out = [0.0] * int((ticks * 0.02 + 0.2) * RATE)
    for k in range(ticks):
        along = k / (ticks - 1)
        pitch = 2350 * (1 + 0.16 * along)
        ring = 0.03 if k == ticks - 1 else 0.004
        at = int(k * 0.02 * RATE)
        for i in range(int(ring * 6 * RATE)):
            t = i / RATE
            loud = min(1.0, t / 0.001) * math.exp(-t / ring)
            out[at + i] += volume * (0.6 + 0.4 * along) * loud * math.sin(2 * math.pi * pitch * t)
    return _write(f"fill-{seconds:.2f}-{volume:.2f}.wav", _fadeOut(out, 0.06))
