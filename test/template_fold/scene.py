#!/usr/bin/env python3

from videocode import *
from titlecard import titleCard

# A line long enough to run past the right edge of the code pane, whatever width the pane is given: its far end is where the pane once drew a blank block instead of the text.
titleCard("One")
titleCard(title="Two", color=RED_A)
square = Square()
wait(200)
