from videocode import *

box = Rectangle(width=3, height=2, fillColor=BLUE_C).position(-3, 0).fadeIn()
wait(1)
box.moveTo(x=2, duration=1)
wait(2)
box.rotateTo(45)
wait(1)
Circle(radius=0.5).position(3, 2)
