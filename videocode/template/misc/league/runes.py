#!/usr/bin/env python3

from __future__ import annotations
from enum import Enum
from videocode.constants import SH, SINGLE_FRAME, SW, url
from videocode.input.interface.Group import Group
from videocode.input.media.WebImage import WebImage
from videocode.utils.easings import Easing

import requests


class Path(Enum):
    Precision = "Precision"
    Domination = "Domination"
    Resolve = "Resolve"
    Sorcery = "Sorcery"
    Inspiration = "Inspiration"


class Rune(Enum):
    # Precision
    LethalTempo = "Lethal Tempo"
    Triumph = "Triumph"
    LegendAlacrity = "Legend- Alacrity"
    LastStand = "Last Stand"

    # Resolve
    ShieldBash = "Shield Bash"
    BonePlating = "Bone Plating"


class Shard(Enum):
    AdaptativeForce = "Adaptive_Force"
    AttackSpeed = "Attack_Speed"
    AbilityHaste = "Ability_Haste"
    MovementSpeed = "Movement_Speed"
    HealthScaling = "Health_Scaling"
    Tenacity = "Tenacity_and_Slow_Resist"


Color: dict[Path, str] = {
    Path.Precision: "Yellow",
    Path.Domination: "Red",
    Path.Resolve: "Green",
    Path.Sorcery: "Blue",
    Path.Inspiration: "Light Blue",
}


class UrlKind(Enum):
    Rune = "File:{name}_rune.png"
    Icon = "File:{name}_icon.png"  # Tree Path
    Shard = "File:Rune_shard_{name}.png"  # Rune Shard

    @staticmethod
    def get(kind: UrlKind, name: str) -> url:
        endpoint = "https://leagueoflegends.fandom.com/api.php"
        params = {
            "action": "query",
            "format": "json",
            "titles": (format := kind.value.format(name=name)),
            "prop": "imageinfo",
            "iiprop": "url",
        }

        response = requests.get(endpoint, params=params)
        data = response.json()

        pages = data.get("query", {}).get("pages", {})
        for page in pages.values():
            if "imageinfo" in page:
                return page["imageinfo"][0]["url"]

        raise ValueError(f"{kind} '{format}' not found.")


class RuneSet:
    def __init__(
        self,
        *,
        main: tuple[Path, Rune, Rune, Rune, Rune],
        sub: tuple[Path, Rune, Rune],
        shard: tuple[Shard, Shard, Shard],
    ) -> None:
        # Y spacing
        runeSpacing = 180
        shardSpacing = 75

        self.x = SW * 0.3
        self.y = SH * 0.25
        self.duration = 0.4

        xDiffSub = SW * 0.3
        yDiffSub = runeSpacing * 0.4

        xDiffShard = xDiffSub
        yDiffShard = runeSpacing * 2.35

        offscreenStart = 2000

        self.main = Group(
            *(
                (
                    (0, idx * runeSpacing + (runeSpacing * 0.25 if idx > 0 else 0)),
                    WebImage(UrlKind.get(UrlKind.Rune, i.value)),
                )
                for idx, i in enumerate(main[1:])
            ),
        )

        self.sub = Group(
            *(
                (
                    (xDiffSub, yDiffSub + idx * runeSpacing),
                    WebImage(UrlKind.get(UrlKind.Rune, i.value)),
                )
                for idx, i in enumerate(sub[1:])
            ),
        )

        self.shard = Group(
            *(
                (
                    (xDiffShard, yDiffShard + idx * shardSpacing),
                    WebImage(UrlKind.get(UrlKind.Shard, i.value)),
                )
                for idx, i in enumerate(shard)
            ),
        )

        self.all = (
            Group(
                self.main,
                self.sub,
                self.shard,
            )
            .position(self.x, self.y + offscreenStart)
            .flush()
        )

    def animate(self):
        self.all.moveTo(self.x, self.y, easing=Easing.Out, start=SINGLE_FRAME, duration=0.4).flush()
        return self


# TODO:
# create a stack that keeps track of the used name
# If you want a thumbnail instead of the original image, use iiurlwidth=100 (or desired width).
# https://static.wikia.nocookie.net/leagueoflegends/images/2/26/Precision_icon.png/revision/latest/scale-to-width-down/52?cb=20170926031126

if __name__ == "__main__":
    r = RuneSet(
        main=(Path.Precision, Rune.LethalTempo, Rune.Triumph, Rune.LegendAlacrity, Rune.LastStand),
        sub=(Path.Resolve, Rune.ShieldBash, Rune.BonePlating),
        shard=(Shard.AdaptativeForce, Shard.AttackSpeed, Shard.HealthScaling),
    )
