from videocode import *


def caption(text: str) -> None:
    Text(text)


def titleCard(title: str, color: rgba = BLUE_C) -> None:
    Rectangle(width=3, height=2, fillColor=color)
    caption(title)
