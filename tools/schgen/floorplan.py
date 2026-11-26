"""The board's floorplan: outline, a stackup the printed filters can live
on, the filters themselves (as footprints tied to their schematic symbols),
and a named region for every block, drawn on the layer User.1.

The project's own placement and routing (the two synthesizers) is left where
it is; the floorplan is built round it."""

import os
import re
import uuid as _uuid

from . import parts
from .sexpr import Q, dump, find, parse, span_of, top_spans

NS = _uuid.UUID("0c0f5d6e-3b0e-4d39-9d55-3a8f2f7c1a02")
LAYER = "User.1"


def _id(name):
    return Q(str(_uuid.uuid5(NS, name)))


# millimetres, in the board file's own coordinates (the synthesizers sit at
# x 97..114, y 68..96 there)
OUTLINE = (18.0, 28.0, 240.0, 154.0)

# reference: (x, y, rotation); the filter's own origin is its centre
FILTERS = {
    "FL202": (74.0, 52.0, 0),      # L2 band-pass, interdigital
    "FL203": (110.0, 47.0, 0),     # image low-pass, 4.0 GHz
    "FL400": (188.0, 72.0, 0),     # IF1 low-pass, 4.0 GHz
    "FL401": (188.0, 89.0, 180),   # IF1 band-pass, hairpin: ports downward
    "FL300": (86.0, 114.0, 0),     # H1 band-pass
    "FL301": (140.0, 114.0, 0),    # H1 low-pass, 5.0 GHz
    "FL302": (84.0, 140.5, 0),     # H2 band-pass
    "FL303": (128.0, 140.5, 0),    # H2 low-pass, 7.0 GHz
}

# name, x0, y0, x1, y1, what goes there
REGIONS = [
    ("RF INPUT", 20, 68, 58, 98,
     "J100 on the edge, C100, D100\nU100 attenuator, U101 band select\n"
     "direct-path low-pass (L100, L101)"),
    ("LOW BAND FRONT END", 60, 30, 148, 64,
     "FL200 FL201 (L1), FL202 (L2), U200\nFL203 image low-pass\n"
     "U201 U202 U203 preamplifier"),
    ("LO1", 94, 66, 116, 80, "as placed"),
    ("LO2", 94, 83, 116, 98, "as placed"),
    ("LO1 DRIVE", 117, 66, 142, 80, "pad, U500, pad"),
    ("LO2 DRIVE", 117, 83, 142, 98, "pad, U550, pad"),
    ("MIX1, IF1 AMP", 143, 64, 168, 80, "U400 U401\npads"),
    ("IF1 FILTERS", 169, 64, 209, 100, "FL400 low-pass, FL401 hairpin"),
    ("MIX2", 143, 83, 168, 98, "U402 select, U403\ndiplexer"),
    ("HIGH BAND FRONT END", 20, 100, 168, 152,
     "U300\nFL300 FL301 (H1)\nFL302 FL303 (H2)\nU301\nU302 U303 U304\n"
     "preamplifier, up the\nright side to U402"),
    ("SECOND IF", 170, 102, 209, 124,
     "U600 U601, U602 attenuator\nanti-alias filter, U603"),
    ("ADC", 170, 126, 209, 152, "U700 driver, U701"),
    ("CLOCK", 211, 126, 238, 152, "Y700, U702"),
    ("CONTROLLER", 211, 60, 238, 124,
     "U800 RP2350B, U801 flash\nJ800 USB-C on the edge\nJ801 SWD"),
    ("POWER", 211, 30, 238, 58, "FB900-902\nU900-904"),
    ("FREE", 150, 30, 209, 62, "kept clear above the first IF:\n"
     "room for a shield can, test points"),
]

# where the RF runs: (name, on F.Cu?, points)
ROUTES = [
    ("input", True, [(18, 83), (52, 83)]),
    ("L1", True, [(52, 81), (58, 81), (58, 38), (88, 38), (88, 46)]),
    ("L2", True, [(52, 82), (60, 82), (60, 55.52), (64.55, 55.52)]),
    ("L2 out", True, [(83.45, 55.52), (88, 55.52), (88, 48)]),
    ("low", True, [(88, 47), (94.47, 47)]),
    ("low out", True, [(125.53, 47), (146, 47), (146, 70), (148, 72)]),
    ("LO1", True, [(114, 73), (148, 73)]),
    ("LO2", True, [(114, 91), (148, 91)]),
    ("IF1", True, [(150, 72), (172.47, 72)]),
    ("IF1 turn", True, [(203.53, 72), (207.5, 72), (207.5, 95.56),
                        (205.08, 95.56)]),
    ("IF1 back", True, [(170.92, 95.56), (160, 95.56), (160, 92),
                        (150, 92)]),
    ("high", True, [(52, 85), (56, 85), (56, 99), (40, 99), (40, 114.06),
                    (50.29, 114.06)]),
    ("H1", True, [(121.71, 114.06), (126.76, 114.06)]),
    ("H1 out", True, [(153.24, 114), (160, 114), (160, 122)]),
    ("H2 in", True, [(40, 114.06), (40, 140.53), (55.45, 140.53)]),
    ("H2", True, [(112.55, 140.53), (117.38, 140.53)]),
    ("H2 out", True, [(138.62, 140.5), (160, 140.5), (160, 122)]),
    ("high up", True, [(160, 122), (163, 118), (163, 100), (160, 96)]),
    ("IF2", False, [(150, 94), (150, 106), (172, 106)]),
]

NOTES = (
    "FLOORPLAN (layer User.1; solid lines: where the RF runs on F.Cu; "
    "dotted: the IF, on In2.Cu).  Stackup: F.Cu / 0.508 mm RO4003C / In1.Cu "
    "ground / prepreg / In2.Cu / FR4 / B.Cu.  The printed filters need the "
    "solid In1.Cu ground under them and nothing else on F.Cu inside their "
    "courtyards.\n50 ohm microstrip on F.Cu is 1.10 mm wide (the filters' "
    "port pads).  Fence each region with ground vias; LO1 and LO2 keep the "
    "project's placement.\nThe 12 MHz IF leaves MIX2 on In2.Cu under the "
    "high band's feed and comes up at the second IF.  IF_DIRECT, REF1/REF2 "
    "and the ADC bus also run on In2.Cu.")

STACKUP = """(stackup
 (layer "F.SilkS" (type "Top Silk Screen"))
 (layer "F.Paste" (type "Top Solder Paste"))
 (layer "F.Mask" (type "Top Solder Mask") (thickness 0.01))
 (layer "F.Cu" (type "copper") (thickness 0.035))
 (layer "dielectric 1" (type "core") (thickness 0.508)
  (material "RO4003C") (epsilon_r 3.55) (loss_tangent 0.0027))
 (layer "In1.Cu" (type "copper") (thickness 0.035))
 (layer "dielectric 2" (type "prepreg") (thickness 0.4)
  (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
 (layer "In2.Cu" (type "copper") (thickness 0.035))
 (layer "dielectric 3" (type "core") (thickness 0.508)
  (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
 (layer "B.Cu" (type "copper") (thickness 0.035))
 (layer "B.Mask" (type "Bottom Solder Mask") (thickness 0.01))
 (layer "B.Paste" (type "Bottom Solder Paste"))
 (layer "B.SilkS" (type "Bottom Silk Screen"))
 (copper_finish "ENIG")
 (dielectric_constraints yes)
)"""


def _text(key, text, x, y, size=1.5, justify="left top", layer=LAYER):
    return ["gr_text", Q(text), ["at", x, y, 0], ["layer", Q(layer)],
            ["uuid", _id("text/" + key)],
            ["effects", ["font", ["size", size, size],
                         ["thickness", round(size * 0.15, 3)]],
             ["justify"] + justify.split()]]


def _rect(key, x0, y0, x1, y1, layer=LAYER, width=0.2, dash=True):
    return ["gr_rect", ["start", x0, y0], ["end", x1, y1],
            ["stroke", ["width", width],
             ["type", "dash" if dash else "solid"]],
            ["fill", "no"], ["layer", Q(layer)], ["uuid", _id("rect/" + key)]]


def _footprint(ref, name, x, y, rot, path, sheetname, sheetfile, value):
    with open(os.path.join(parts.REPO, "sim", "filters",
                           name + ".kicad_mod"), encoding="utf-8") as fh:
        src = parse(fh.read())
    out = ["footprint", Q("spectre_filters:" + name), ["layer", Q("F.Cu")],
           ["uuid", _id("fp/" + ref)], ["at", x, y, rot]]
    out.append(find(src, "descr"))
    tie = tie_groups(name, src)
    n = 0
    for item in src[2:]:
        if not isinstance(item, list) or item[0] in (
                "version", "generator", "generator_version", "layer",
                "descr"):
            continue
        item = [list(x) if isinstance(x, list) else x for x in item]
        n += 1
        for i, x in enumerate(item):
            if isinstance(x, list) and x[0] == "uuid":
                item[i] = ["uuid", _id("fp/%s/%d" % (ref, n))]
        if item[0] == "property":
            if item[1] == "Reference":
                item[2] = Q(ref)
            elif item[1] == "Value":
                item[2] = Q(value)
            at = find(item, "at")
            at[3:] = [rot]
        if item[0] == "pad":
            at = find(item, "at")
            a = (float(at[3]) if len(at) > 3 else 0.0) + rot
            at[3:] = [a % 360]
        if item[0] == "attr":
            out += [["path", Q(path)], ["sheetname", Q(sheetname)],
                    ["sheetfile", Q(sheetfile)]]
        out.append(item)
        if item[0] == "attr":
            # the filter's copper joins its pads on purpose
            out.append(["net_tie_pad_groups"] + [Q(x) for x in tie])
    return out


def tie_groups(name, src):
    """Which pads a filter's own copper joins: all of them, except in the
    hairpin, whose ports only couple to each other."""
    pads = sorted({str(x[1]) for x in src
                   if isinstance(x, list) and x[0] == "pad"})
    return pads if "hairpin" in name else [", ".join(pads)]


def filters_of(sheets):
    """{reference: (footprint name, path, sheet name, sheet file, value)}
    of the printed filters in the schematic."""
    found = {}
    for s in sheets.values():
        for inst in s.insts:
            fp = inst.fields.get("Footprint", "")
            if fp.startswith("spectre_filters:"):
                found[inst.ref] = (fp.split(":")[1],
                                   "/%s/%s" % (s.paths[0], inst.uuid),
                                   "/%s/" % s.names[0], s.filename,
                                   inst.fields["Value"])
    return found


def apply(pcb_text, sheets):
    """The board file with the floorplan added (or brought up to date)."""
    t = parse(pcb_text)
    mine = set()
    add = []

    def put(node):
        add.append(node)
        mine.add(str(find(node, "uuid")[1]))

    x0, y0, x1, y1 = OUTLINE
    put(_rect("outline", x0, y0, x1, y1, "Edge.Cuts", 0.1, dash=False))
    for name, a, b, c, d, what in REGIONS:
        put(_rect(name, a, b, c, d))
        put(_text(name, name, a + 1.0, b + 1.0, 1.6))
        put(_text(name + "/what", what, a + 1.0, b + 4.0, 1.0))
    for name, top, pts in ROUTES:
        for i, (a, b) in enumerate(zip(pts, pts[1:])):
            put(["gr_line", ["start", a[0], a[1]], ["end", b[0], b[1]],
                 ["stroke", ["width", 0.4],
                  ["type", "solid" if top else "dot"]],
                 ["layer", Q(LAYER)],
                 ["uuid", _id("route/%s/%d" % (name, i))]])
    put(_text("notes", NOTES, x0, y1 + 3.0, 1.6))
    put(_text("title", "SPECTRE 6.4 GHz proposal: floorplan, %g x %g mm"
              % (x1 - x0, y1 - y0), x0, y0 - 3.0, 2.5, "left bottom"))
    for ref, (name, path, sheetname, sheetfile, value) in sorted(
            filters_of(sheets).items()):
        x, y, rot = FILTERS[ref]
        put(_footprint(ref, name, x, y, rot, path, sheetname, sheetfile,
                       value))
    # ground under everything, on the layer below the filters
    put(["zone", ["net", Q("GND")], ["layer", Q("In1.Cu")],
         ["uuid", _id("zone/in1")], ["name", Q("GND under the filters")],
         ["hatch", "edge", 0.5], ["connect_pads", "yes", ["clearance", 0.2]],
         ["min_thickness", 0.2], ["filled_areas_thickness", "no"],
         ["fill", ["thermal_gap", 0.3], ["thermal_bridge_width", 0.3]],
         ["polygon", ["pts", ["xy", x0, y0], ["xy", x1, y0], ["xy", x1, y1],
                      ["xy", x0, y1]]]])

    return _merge(pcb_text, add, mine)


def _merge(text, add, mine):
    """The additions put into the board file's text; everything of the
    project's own stays byte for byte as it was."""
    # an earlier run's additions go first
    for token, a, b in reversed(top_spans(text)):
        if token in ("gr_rect", "gr_text", "footprint", "zone", "gr_line"):
            m = re.search(r'\(uuid "([^"]+)"\)', text[a:b])
            if m and m.group(1) in mine:
                a0 = a
                while text[a0 - 1] in " \t":
                    a0 -= 1
                text = text[:a0 - 1] + text[b:] if text[a0 - 1] == "\n" \
                    else text[:a] + text[b:]
    a, b = span_of(text, "layers")
    layers = text[a:b]
    if '"In1.Cu"' not in layers:
        layers = layers.replace('\t\t(2 "B.Cu" signal)',
                                '\t\t(4 "In1.Cu" signal)\n\t\t(6 "In2.Cu" '
                                'signal)\n\t\t(2 "B.Cu" signal)')
    layers = layers.replace('(39 "User.1" user)',
                            '(39 "User.1" user "Floorplan")')
    text = text[:a] + layers + text[b:]
    a, b = span_of(text, "stackup")
    text = text[:a] + dump(parse(STACKUP), 2).lstrip("\t") + text[b:]
    block = "".join(dump(node, 1) + "\n" for node in add)
    spans = [x for x in top_spans(text) if x[0] in ("embedded_fonts",
                                                    "embedded_files")]
    at = spans[0][1] if spans else text.rindex(")")
    while text[at - 1] in " \t":
        at -= 1
    return text[:at] + block + text[at:]
