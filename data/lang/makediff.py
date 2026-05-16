"""
Make a diff between two files.
For the file names, please refer to data/bin_patch.json
"""

import zlib
import json

def make_diff(original, replace, export, path=None):
    Original = open(original, "rb").read()
    New = open(replace, "rb").read()
    f = json.load(open("data/bin_patch.json"))
    s, e = [int(x, 16) for x in f[export]]
    seg = bytearray([o ^ n for o, n in zip(Original[s:e], New[s:e])])
    diff = zlib.compress(seg)
    if path:
        export = f"{path}/{export}"
    with open(export, "wb") as f:
        f.write(diff)

def get_ia4(frm, export, start=0, size=0, path=None):
    with open(frm, "rb") as f:
        orig = f.read()
    end=start+size
    w=orig[start:end]
    if path:
        export = f"{path}/{export}"
    with open(export,"wb") as f:
        f.write(w)

diff_list = [
    "NESFont.bin"
#     "title.bin",
#     "EXTitleCard.bin",
#     "Gameover.bin",
#     "TitleCardEN.bin",
#     "ItemNameEN.bin",
#     "MapName.bin",
#     "ActionEN.bin",
#     "PlaceName.bin",
#     "FileSelEN.bin",
#     "KingDodongo.bin",
#     "Gohma.bin",
#     "PhantomGanon.bin",
#     "Barinade.bin",
#     "Volvagia.bin",
#     "Morpha.bin",
#     "Twinrova.bin",
#     "Ganondorf.bin",
#     "Bongo.bin",
#     "Ganon.bin"
]
for file in diff_list:
    make_diff("data/lang/baserom.z64", "data/lang/oot-ntsc-1.0.z64", file, path="data/lang/Verdhesk")
    
# get_ia4("baserom-decomp.z64", "blue_fire_arrow_item_name_eng.ia4", 0x8A1C00, 0x400, path="data/lang/Verdhesk")

# get_ia4("baserom-decomp.z64","blue_fire_arrow_item_name_jap.ia4",0x883000,0x400, path="data/lang/Verdhesk")
