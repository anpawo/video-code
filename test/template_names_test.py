#!/usr/bin/env python3
"""
The name a template's clip is given, for each way a template can be written.

A function is named after itself; a class after the class, not `__init__`; a
method after the method, not its class; a module that makes inputs as it is
imported, after the module. Run through `execSource`, the editor's own entry,
with the template files written beside the scene.

Run directly: `python3 test/template_names_test.py`
"""

import os
import sys
import tempfile

sys.path.insert(0, ".")
sys.path.insert(0, "test")

from helpers import check, section, summary  # noqa: E402
from videocode.context import Context  # noqa: E402
from videocode.serialize import execSource  # noqa: E402

folder = tempfile.mkdtemp(prefix="vc-template-names-")
FILES = {
    "names_kit.py": """\
from videocode import *


def badge():
    Circle()


class Card:
    def __init__(self):
        Rectangle(width=2, height=1)

    def stamp(self):
        Square()
""",
    "names_banner.py": """\
from videocode import *

Square(side=1)
""",
}
for name, text in FILES.items():
    with open(os.path.join(folder, name), "w") as f:
        f.write(text)

SCENE = os.path.join(folder, "scene.py")
SOURCE = """\
from videocode import *
from names_kit import badge, Card
import names_banner

badge()
Card().stamp()
"""

result = execSource(SOURCE, SCENE)
chains = list(Context.template.values())
# (line of the scene, name) of each chain's first call: the one written in the scene.
names = {(chain[0][1], chain[0][2]) for chain in chains}

section("the scene runs, and every input it made through a template is traced to it")
check("the scene runs", result["ok"])
check("each chain starts in the scene", bool(chains) and all(chain[0][0] == SCENE for chain in chains))

section("each kind of template is named the way it is written")
check("a module made on import is named after the module", (3, "names_banner") in names)
check("a function is named after itself", (5, "badge") in names)
check("a class is named after the class, not __init__", (6, "Card") in names)
check("a method is named after the method, not its class", (6, "stamp") in names)
check("and nothing else is taken for a template", names == {(3, "names_banner"), (5, "badge"), (6, "Card"), (6, "stamp")})
check("a class records its __init__, where its parameters are read", any(c[0][3] == "names_kit:Card.__init__" for c in chains))

summary()
