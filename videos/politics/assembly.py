"""
A vote read out on the chamber: the half-ring of seats, then each group's label landing and its
seats coming on, green for a yes and red for a no, each with its two sounds.

    ./video-code --file videos/politics/assembly.py --width 1080 --height 1920 --generate assembly.mp4
    ./video-code --file videos/politics/assembly.py --width 1080 --height 1920 --generate assembly-reel.mp4 --set sounds=reel

`sounds=drawn` (the default) plays the two sounds written out as waves in sfx.py. `sounds=reel`
plays the clips cut from the reference Reel instead, which are not committed (videos/politics/ref).

The seat counts are a stand-in close to the 2024 chamber, there to fill the picture; a real
scene takes the day's figures, and the number who voted, from the public vote it shows.
"""

from videocode import *
from videocode.template.effect.other.popIn import popIn
from videocode.template.input.Hemicycle import Hemicycle
from videos.politics.sfx import fill, pop

PAPER = rgba(236, 233, 223)
YES, YES_TAG = rgba(78, 203, 113), rgba(46, 158, 91)
NO, NO_TAG = rgba(229, 72, 77), rgba(200, 50, 43)

# left of the picture to right
GROUPS = {
    "GDR": 17, "LFI": 71, "ECO": 38, "SOC": 66, "LIOT": 23, "DEM": 36,
    "EPR": 91, "HOR": 34, "DR": 49, "UDR": 16, "RN": 123, "NI": 13,
}  # fmt: skip

REEL = "videos/politics/ref/DeYcNPoOYMr/sfx/recut/kit"
sounds = param("sounds", "drawn")

Rectangle(width=W, height=H, fillColor=PAPER, strokeColor=TRANSPARENT)
chamber = Hemicycle(GROUPS, width=6.9).position(y=1.0).fadeIn(duration=0.4)

cardLeft = -chamber.width / 2
cardBottom = 1.0 - chamber.height / 2


def vote(group: str, says: str, yes: bool, voted: int, at: sec) -> None:
    """The label lands with its pop, the seats come on behind it, and the trill closes the wave."""
    wave = 0.6
    label = Text(f"{group} · {says}", fontSize=0.2, fillColor=WHITE, bold=True)
    # from the first letter's edge to the last one's: a text's own width leaves its spaces out
    first, last = label.inputs[0], label.inputs[-1]
    span = (last.meta.position.x + last.width / 2) - (first.meta.position.x - first.width / 2)
    plate = Rectangle(
        width=span + 0.4, height=0.44, fillColor=YES_TAG if yes else NO_TAG, strokeColor=TRANSPARENT, cornerRadius=8
    )
    # a yes hangs from the card's left corner, a no from its right one
    x = (cardLeft + plate.width / 2 + 0.24) * (1 if yes else -1)
    label.inFrontOf(plate)
    Group(plate, label).position(x=x, y=cardBottom - 0.1).opacity(0).apply(popIn(start=at, duration=0.35))

    chamber.light(group, YES if yes else NO, count=voted, start=at + 0.12, duration=wave)

    trill = max(0.12, min(wave, voted * 0.006))
    if sounds == "reel":
        Sound(f"{REEL}/tag-pop.wav", start=at, volume=0.9)
        Sound(f"{REEL}/seat-fill.wav", start=at + 0.12 + wave - 0.2, volume=0.9)
    else:
        Sound(pop(), start=at)
        Sound(fill(trill), start=at + 0.12 + wave - trill)


vote("LFI", "POUR", True, 71, at=1.0)
vote("RN", "CONTRE", False, 76, at=2.6)

wait(1.2)
