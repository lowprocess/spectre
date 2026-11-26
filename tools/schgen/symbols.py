"""Symbols: KiCad's own (read from its installed libraries, with `extends`
flattened), the project's existing ones (lifted out of its schematics), and
new ones drawn here as boxes with pins."""

import copy
import os

from .sexpr import Q, find, find_all, parse

KICAD_SYMBOLS = os.environ.get("KICAD10_SYMBOL_DIR", "/usr/share/kicad/symbols")
P = 2.54                      # the schematic grid, mm

_cache = {}


def _lib(path):
    if path not in _cache:
        with open(path, encoding="utf-8") as fh:
            _cache[path] = parse(fh.read())
    return _cache[path]


def _named(lib, name):
    for s in find_all(lib, "symbol"):
        if s[1] == name:
            return s
    raise KeyError(name)


def _prop(sym, key, value=None):
    for p in find_all(sym, "property"):
        if p[1] == key:
            if value is not None:
                p[2] = Q(value)
            return p
    return None


def standard(lib_name, name, rename=None):
    """A symbol from KiCad's libraries, as it is embedded in a schematic:
    named "lib:name", its base symbol's graphics and pins folded in."""
    lib = _lib(os.path.join(KICAD_SYMBOLS, lib_name + ".kicad_sym"))
    sym = copy.deepcopy(_named(lib, name))
    ext = find(sym, "extends")
    if ext is not None:
        base = copy.deepcopy(_named(lib, ext[1]))
        if find(base, "extends") is not None:
            raise ValueError("%s: two levels of extends" % name)
        props = {p[1]: p for p in find_all(sym, "property")}
        out = [x for x in base
               if not (isinstance(x, list) and x[0] == "property")]
        merged = [props.pop(p[1], p) for p in find_all(base, "property")]
        merged += list(props.values())
        # the properties go where the base's were: after its flags
        at = next(i for i, x in enumerate(out)
                  if isinstance(x, list) and x[0] == "symbol")
        out[at:at] = merged
        for unit in find_all(out, "symbol"):
            unit[1] = Q(name + unit[1][len(ext[1]):])
        sym = out
    final = rename or name
    if final != name:
        for unit in find_all(sym, "symbol"):
            unit[1] = Q(final + unit[1][len(name):])
        _prop(sym, "Value", final)
    sym[1] = Q("%s:%s" % (lib_name, final))
    return sym


def lifted(sch_path, lib_id):
    """A symbol as an existing schematic of the project embeds it."""
    with open(sch_path, encoding="utf-8") as fh:
        tree = parse(fh.read())
    for s in find_all(find(tree, "lib_symbols"), "symbol"):
        if s[1] == lib_id:
            return copy.deepcopy(s)
    raise KeyError(lib_id)


def pins_of(sym, unit=None):
    """{number: (x, y, angle, name, type)} of a symbol (of one unit of it,
    with the pins common to all units), and {name: number}, the first of
    each name."""
    pins = {}
    for sub in find_all(sym, "symbol"):
        u = int(str(sub[1]).rsplit("_", 2)[1])
        if unit is not None and u not in (0, unit):
            continue
        for p in find_all(sub, "pin"):
            at = find(p, "at")
            num = str(find(p, "number")[1])
            pins[num] = (float(at[1]), float(at[2]), int(float(at[3])),
                         str(find(p, "name")[1]), p[1])
    names = {}
    for num, (_, _, _, name, _) in pins.items():
        names.setdefault(name, num)       # the first: the one drawn
    return pins, names


# ------------------------------------------------------------- new symbols

def _effects(size=1.27, justify=None, hide=False):
    e = ["effects", ["font", ["size", size, size]]]
    if justify:
        e.append(["justify"] + justify.split())
    return e


def _property(key, value, x=0.0, y=0.0, hide=False, justify=None):
    p = ["property", Q(key), Q(value), ["at", x, y, 0], ["show_name", "no"],
         ["do_not_autoplace", "no"]]
    if hide:
        p.append(["hide", "yes"])
    p.append(_effects(justify=justify))
    return p


def _pin(etype, x, y, angle, name, number, length=P, hide=False):
    p = ["pin", etype, "line", ["at", x, y, angle], ["length", length]]
    if hide:
        p.append(["hide", "yes"])
    p += [["name", Q(name), _effects()], ["number", Q(number), _effects()]]
    return p


def _line(pts, width=0.0):
    return ["polyline", ["pts"] + [["xy", x, y] for x, y in pts],
            ["stroke", ["width", width], ["type", "default"]],
            ["fill", ["type", "none"]]]


def _rect(x0, y0, x1, y1, fill="background", width=0.254):
    return ["rectangle", ["start", x0, y0], ["end", x1, y1],
            ["stroke", ["width", width], ["type", "default"]],
            ["fill", ["type", fill]]]


def _circle(x, y, r, width=0.254, fill="background"):
    return ["circle", ["center", x, y], ["radius", r],
            ["stroke", ["width", width], ["type", "default"]],
            ["fill", ["type", fill]]]


def _shell(lib_id, ref, value, footprint, datasheet, description, extra,
           graphics, pins, ref_at, val_at, pin_names=True, pin_numbers=True,
           power=False, offset=1.016):
    name = lib_id.split(":")[1]
    s = ["symbol", Q(lib_id)]
    if power:
        s.append(["power", "global"])
    if not pin_numbers:
        s.append(["pin_numbers", ["hide", "yes"]])
    s.append(["pin_names", ["offset", offset]]
             + ([] if pin_names else [["hide", "yes"]]))
    s += [["exclude_from_sim", "no"], ["in_bom", "no" if power else "yes"],
          ["on_board", "yes"], ["in_pos_files", "yes"],
          ["duplicate_pin_numbers_are_jumpers", "no"],
          _property("Reference", ref, *ref_at, hide=power, justify="left"),
          _property("Value", value, *val_at, justify="left"),
          _property("Footprint", footprint, hide=True),
          _property("Datasheet", datasheet, hide=True),
          _property("Description", description, hide=True)]
    for k, v in (extra or {}).items():
        s.append(_property(k, v, hide=True))
    s.append(["symbol", Q(name + "_0_1")] + graphics)
    s.append(["symbol", Q(name + "_1_1")] + pins)
    s.append(["embedded_fonts", "no"])
    return s


def box(lib_id, value, left=(), right=(), top=(), bottom=(), ref="U",
        footprint="", datasheet="", description="", extra=None, width=None,
        glyph=None, min_height=0, pin_length=P):
    """An IC as a box.  Each side is a list of pins (number, name, type), a
    None for a gap; a number may be several, "5,6,8": the first is drawn and
    the rest sit hidden on it (ground pins).  Left and right pins run down
    from the top; top and bottom pins run left to right."""
    def chars(side):
        return max([len(p[1]) for p in side if p] or [0])
    rows = max(len(left), len(right), 1)
    cols = max(len(top), len(bottom), 0)
    if width is None:
        need = (chars(left) + chars(right)) * 1.1 + 6
        # the top pins sit to the right, clear of the reference and value
        need = max(need, (cols + 1) * P + (len(value) * 1.3 if top else 0),
                   (len(bottom) + 1) * P, 4 * P)
        width = P * 2 * round((need / 2) / P + 0.49)
    height = max((rows + 1) * P, min_height)
    if top or bottom:
        height += (chars(top) + chars(bottom)) * 1.1
    height = P * 2 * round((height / 2) / P + 0.49)
    hx, hy = width / 2, height / 2
    pins = []

    def add(etype, x, y, angle, name, number):
        nums = str(number).split(",")
        ln = pin_length if angle in (0, 180) else P
        pins.append(_pin(etype, x, y, angle, name, nums[0], ln))
        for n in nums[1:]:
            pins.append(_pin("passive", x, y, angle, name, n, ln,
                             hide=True))

    def column(side, x, angle):
        y0 = (len(side) - 1) / 2 * P
        for i, p in enumerate(side):
            if p:
                add(p[2], x, _grid(y0 - i * P), angle, p[1], p[0])

    def row(side, y, angle):
        x0 = -(len(side) - 1) / 2 * P
        for i, p in enumerate(side):
            if p:
                add(p[2], _grid(x0 + i * P), y, angle, p[1], p[0])

    column(left, -hx - pin_length, 0)
    column(right, hx + pin_length, 180)
    for i, p in enumerate(top):
        if p:
            add(p[2], _grid(hx - (len(top) - i) * P), hy + P, 270, p[1], p[0])
    row(bottom, -hy - P, 90)
    graphics = [_rect(-hx, hy, hx, -hy)] + (glyph or [])
    return _shell(lib_id, ref, value, footprint, datasheet, description,
                  extra, graphics, pins, (-hx, hy + 3.3), (-hx, hy + 1.3))


def _grid(v):
    return round(v / (P / 2)) * (P / 2)


def two_pin(lib_id, kind, value="", ref=None, footprint="", description=""):
    """A resistor, capacitor, inductor, ferrite bead or TVS diode, drawn
    upright in the style of the project's own passives: pin 1 on top, the
    pins 5.08 mm apart."""
    if kind in ("R", "FB"):
        g = [_rect(-0.762, 1.778, 0.762, -1.778, fill="none", width=0.2032)]
        if kind == "FB":
            g.append(_line([(-1.27, -0.889), (1.27, 0.889)], 0.2032))
        ln = 0.762
    elif kind == "C":
        g = [_line([(-1.524, 0.508), (1.524, 0.508)], 0.3048),
             _line([(-1.524, -0.508), (1.524, -0.508)], 0.3048)]
        ln = 2.032
    elif kind == "D":
        g = [_line([(-1.27, 0.635), (1.27, 0.635)], 0.2032),
             _line([(-1.27, -0.635), (1.27, -0.635)], 0.2032),
             _line([(-1.27, 0.635), (-1.27, 0.9)], 0.2032),
             _line([(1.27, -0.635), (1.27, -0.9)], 0.2032),
             _line([(-1.016, 1.778), (1.016, 1.778), (0, 0.635),
                    (-1.016, 1.778)], 0.2032),
             _line([(-1.016, -1.778), (1.016, -1.778), (0, -0.635),
                    (-1.016, -1.778)], 0.2032)]
        ln = 0.762
    else:
        g = [["arc", ["start", 0, y0], ["mid", 0.4445, y0 + 0.4445],
              ["end", 0, y0 + 0.889],
              ["stroke", ["width", 0.2032], ["type", "default"]],
              ["fill", ["type", "none"]]]
             for y0 in (-1.778, -0.889, 0, 0.889)]
        ln = 0.762
    pins = [_pin("passive", 0, 2.54, 270, "", "1", ln),
            _pin("passive", 0, -2.54, 90, "", "2", ln)]
    return _shell(lib_id, ref or kind, value, footprint, "", description,
                  {"IPN": "", "PartNumber": "", "Manufacturer": ""}, g, pins,
                  (1.905, 1.27), (1.905, -1.27), pin_names=False,
                  pin_numbers=False, offset=0)


def rail(lib_id, net):
    """A supply-rail symbol: an arrow, and a global net of its name."""
    g = [_line([(0, 0), (0, 1.27)]),
         _line([(-0.762, 1.27), (0, 2.54), (0.762, 1.27), (-0.762, 1.27)])]
    pin = ["pin", "power_in", "line", ["at", 0, 0, 90], ["length", 0],
           ["name", Q(""), _effects()], ["number", Q("1"), _effects()]]
    s = _shell(lib_id, "#PWR", net, "", "", "Power symbol creates a global "
               "label with name \"%s\"" % net, None, g, [pin], (0, -3.81),
               (0, 3.556), pin_names=False, pin_numbers=False, power=True,
               offset=0)
    _prop(s, "Value")[-1] = _effects(justify=None)
    return s


def flag(lib_id="power:PWR_FLAG"):
    return standard("power", "PWR_FLAG")


# little pictures for the inside of a box, in the project's root-sheet style
def lowpass_glyph(w=3.0):
    return [_line([(-w, 0.9), (0.6, 0.9), (w, -1.5)], 0.2)]


def bandpass_glyph(w=3.0):
    return [_line([(-w, -1.5), (-1.5, 0.9), (1.5, 0.9), (w, -1.5)], 0.2)]


def amp_glyph(s=2.2):
    return [_line([(-s, s), (-s, -s), (s, 0), (-s, s)], 0.2)]


def att_glyph(s=2.2):
    return [_rect(-s, s * 0.45, s, -s * 0.45, fill="none", width=0.2),
            _line([(-s * 0.8, -s), (s * 0.8, s)], 0.2)]


def switch_glyph(n, x=0.0, span=None):
    """A wiper from the left to the first of n throws on the right."""
    span = span or (n - 1) * P
    ys = [span / 2 - i * span / max(n - 1, 1) for i in range(n)]
    g = [_circle(x - 2.2, 0, 0.3, 0.2, "none")]
    for y in ys:
        g.append(_circle(x + 2.2, y, 0.3, 0.2, "none"))
    g.append(_line([(x - 1.9, 0.1), (x + 1.9, ys[0])], 0.2))
    return g
