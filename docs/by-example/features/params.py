"""
#366 — `param(name, default)` : une scène écrite une fois, remplie du dehors.

    ./video-code --editor   --file docs/by-example/features/params.py
    ./video-code --file docs/by-example/features/params.py --generate hello.mp4 --set name=Ada --set score=12
    ./video-code --file docs/by-example/features/params.py --generate "out/{name}.mp4" --data docs/by-example/features/params.csv
    ./video-code --lint     --file docs/by-example/features/params.py --data docs/by-example/features/params.csv

Sans rien donner, la scène tourne avec ses valeurs par défaut. Le type du
défaut est celui du paramètre : "12" arrive en int, "#ff8800" en rgba.
"""

from videocode import *

name = param("name", "World")   # un str
score = param("score", 0)       # "12" arrive en 12
brand = param("brand", BLUE_C)  # "#ff8800" arrive en rgba

Text(text=f"Hello, {name}!", fontSize=0.9, fillColor=brand).position(0, 0.6).fadeIn(duration=0.5)

points = Text(text=f"{score} points", fontSize=0.5, fillColor=WHITE).position(0, -0.6).opacity(0)
points.fadeIn(start=0.4, duration=0.5)

wait(2)
