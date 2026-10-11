"""
Locke top, his rune page on the runes template. The art and the icons are the game's own
(Data Dragon); they live in media/, which is not committed.

    ./video-code --file videos/lol/locke_runes.py --generate locke_runes.mp4
"""

from videocode import *
from videos.lol.runes import Row, Tree, runePage

MEDIA = "videos/lol/media/locke"


def icons(*ids: int) -> list[str]:
    return [f"{MEDIA}/runes/{i}.png" for i in ids]


runePage(
    champion="LOCKE",
    title="THE ASHEN EXORCIST",
    lane="TOP LANE",
    patch="RUNE PAGE · PATCH 26.19",
    splash=f"{MEDIA}/splash.jpg",
    primary=Tree("DOMINATION", f"{MEDIA}/runes/tree-8100.png", rgba(212, 66, 66), [
        Row(icons(8112, 8128, 9923), pick=0, name="ELECTROCUTE"),
        Row(icons(8126, 8139, 8143), pick=2, name="SUDDEN IMPACT"),
        Row(icons(8137, 8140, 8141), pick=1, name="GRISLY MEMENTOS"),
        Row(icons(8135, 8105, 8106), pick=0, name="TREASURE HUNTER"),
    ]),
    secondary=Tree("PRECISION", f"{MEDIA}/runes/tree-8000.png", rgba(200, 170, 110), [
        Row(icons(9101, 9111, 8009), pick=1, name="TRIUMPH"),
        Row(icons(9104, 9105, 9103)),
        Row(icons(8014, 8017, 8299), pick=1, name="CUT DOWN"),
    ]),
    shards=[
        Row(icons(5008, 5005, 5007), pick=2, name="ABILITY HASTE"),
        Row(icons(5008, 5010, 5001), pick=0, name="ADAPTIVE FORCE"),
        Row(icons(5011, 5013, 5001), pick=0, name="HEALTH"),
    ],
)
