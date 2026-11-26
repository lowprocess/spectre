"""A schematic sheet under construction: symbols placed on the 1.27 mm grid,
wires between their pins, labels, and the file written in KiCad 10's format.

Coordinates are the sheet's: millimetres, y down."""

import uuid as _uuid

from .sexpr import Q, dump, find, find_all
from .symbols import pins_of

G = 1.27
VERSION = "20260306"
NS = _uuid.UUID("5bd1f6c8-51a0-4d2e-9f43-6a3d1c0e7b11")


def g(v):
    """Onto the grid."""
    return round(round(v / G) * G, 4)


def _effects(justify=None, size=1.27, bold=False):
    font = ["font", ["size", size, size]]
    if bold:
        font.append(["bold", "yes"])
    e = ["effects", font]
    if justify:
        e.append(["justify"] + justify.split())
    return e


def _stroke(width=0):
    return ["stroke", ["width", width], ["type", "default"]]


class Inst:
    """A placed symbol."""

    def __init__(self, sheet, sym, x, y, rot, mirror=False, unit=1):
        self.sheet, self.sym, self.x, self.y, self.rot = sheet, sym, x, y, rot
        self.mirror = mirror      # left to right; only with rot 0
        self.pins, self.names = pins_of(sym, unit)
        self.ref = self.refs = None

    def _xy(self, px, py):
        if self.mirror:
            px = -px
        dx, dy = {0: (px, -py), 90: (-py, -px), 180: (-px, py),
                  270: (py, px)}[self.rot]
        return (g(self.x + dx), g(self.y + dy))

    def pin(self, key):
        """Where the pin of this number, or of this (unique) name, ends."""
        key = str(key)
        num = key if key in self.pins else self.names[key]
        return self._xy(*self.pins[num][:2])

    def side(self, key):
        """Which way a wire leaves this pin: 'l', 'r', 'u' or 'd'."""
        key = str(key)
        num = key if key in self.pins else self.names[key]
        angle = (self.pins[num][2] + self.rot) % 360
        if self.mirror and angle in (0, 180):
            angle = 180 - angle
        # a pin's angle points from its end to the body
        return {0: "l", 180: "r", 90: "d", 270: "u"}[angle]


class Design:
    def __init__(self, project, root_uuid):
        self.project, self.root_uuid = project, root_uuid
        self.sheets, self.pwr = [], 0
        self.refs = {}

    def path(self, sheet_path):
        """The hierarchical path of a sheet instance ("" is the root)."""
        return "/" + self.root_uuid + ("/" + sheet_path if sheet_path else "")

    def next_pwr(self):
        self.pwr += 1
        return "#PWR%04d" % (1000 + self.pwr)


class Sheet:
    def __init__(self, design, filename, title, paper="A3", base=100,
                 paths=None, bases=None):
        """paths: the hierarchical paths this sheet file is instanced at
        (uuid strings under the root), one for an ordinary sheet; bases: the
        first reference number of each instance."""
        self.d, self.filename, self.title, self.paper = (design, filename,
                                                         title, paper)
        self.paths = paths or [str(_uuid.uuid5(NS, "sheet/" + filename))]
        self.uuid = (design.root_uuid if self.paths == [""]
                     else str(_uuid.uuid5(NS, filename)))
        self.extra = []           # whole nodes appended as they are
        self.raw_tail = ""
        self.bases = bases or [base]
        self.items, self.libs, self.count, self.n = [], {}, {}, 0
        self.hier = []            # (name, shape) of its hierarchical labels
        self.insts = []
        self.drawn = set()
        design.sheets.append(self)

    def _id(self):
        self.n += 1
        return Q(str(_uuid.uuid5(NS, "%s/%d" % (self.filename, self.n))))

    # ------------------------------------------------------------- symbols

    def place(self, sym, x, y, rot=0, value=None, ref=None, fields=None,
              ref_at=None, val_at=None, show_value=True, justify="left",
              dnp=False, mirror=False, show=(), unit=1, of=None):
        """of: an earlier unit of the same part, whose reference this
        one shares."""
        lib_id = str(sym[1])
        self.libs[lib_id] = sym
        inst = Inst(self, sym, g(x), g(y), rot, mirror, unit)
        props = {str(p[1]): p for p in find_all(sym, "property")}
        prefix = ref or str(props["Reference"][2])
        power = prefix.startswith("#")
        if of is not None:
            refs = of.refs
        elif power:
            refs = [self.d.next_pwr() for _ in self.paths]
        else:
            k = self.count.get(prefix, 0)
            self.count[prefix] = k + 1
            refs = ["%s%d" % (prefix, b + k) for b in self.bases]
        inst.ref, inst.refs = refs[0], refs
        vals = {k: str(p[2]) for k, p in props.items()}
        if value is not None:
            vals["Value"] = value
        vals.update(fields or {})
        inst.uuid, inst.fields = str(self._id()), vals
        s = ["symbol", ["lib_id", Q(lib_id)], ["at", inst.x, inst.y, rot]]
        if mirror:
            s.append(["mirror", "y"])
        s += [["unit", unit], ["body_style", 1], ["exclude_from_sim", "no"],
             ["in_bom", "no" if power else "yes"], ["on_board", "yes"],
             ["in_pos_files", "yes"], ["dnp", "yes" if dnp else "no"],
             ["uuid", Q(inst.uuid)]]
        if not isinstance(justify, (tuple, list)):
            justify = (justify, justify)

        def at_of(key, given):
            if given is not None:
                return (round(inst.x + given[0], 3),
                        round(inst.y + given[1], 3))
            a = find(props[key], "at")
            # KiCad draws a mirrored symbol's text with its justification
            # swapped, which is what is wanted: the text mirrors with it
            return inst._xy(float(a[1]), float(a[2])) if rot == 0 else (
                inst.x, inst.y)
        for key in vals:
            hidden = (key not in ("Reference", "Value") + tuple(show)
                      or (key == "Reference" and power)
                      or (key == "Value" and not show_value))
            if key in props and find(props[key], "hide") and key == "Value":
                hidden = hidden
            px, py = (at_of(key, ref_at if key == "Reference" else val_at)
                      if key in ("Reference", "Value") else (inst.x, inst.y))
            p = ["property", Q(key), Q(refs[0] if key == "Reference"
                                       else vals[key]),
                 ["at", px, py, 90 if rot in (90, 270) else 0],
                 ["show_name", "no"],
                 ["do_not_autoplace", "no"]]
            if hidden:
                p.append(["hide", "yes"])
            p.append(_effects(justify[key == "Value"]
                              if key in ("Reference", "Value") and not power
                              else None))
            s.append(p)
        for num in inst.pins:
            s.append(["pin", Q(num), ["uuid", self._id()]])
        s.append(["instances", ["project", Q(self.d.project)] + [
            ["path", Q(self.d.path(path)), ["reference", Q(r)],
             ["unit", unit]]
            for path, r in zip(self.paths, refs)]])
        self.items.append(s)
        self.insts.append(inst)
        return inst

    # --------------------------------------------------------------- wires

    def wire(self, *pts, bus=False):
        pts = [(g(x), g(y)) for x, y in pts]
        for a, b in zip(pts, pts[1:]):
            if a != b and frozenset((a, b)) not in self.drawn:
                self.drawn.add(frozenset((a, b)))
                self.items.append(["bus" if bus else "wire",
                                   ["pts", ["xy", *a], ["xy", *b]],
                                   _stroke(), ["uuid", self._id()]])
        return pts[-1]

    def hv(self, a, b, bus=False):
        """a to b: across, then up or down."""
        return self.wire(a, (b[0], a[1]), b, bus=bus)

    def vh(self, a, b, bus=False):
        """a to b: up or down, then across."""
        return self.wire(a, (a[0], b[1]), b, bus=bus)

    def junction(self, pt):
        self.items.append(["junction", ["at", g(pt[0]), g(pt[1])],
                           ["diameter", 0], ["color", 0, 0, 0, 0],
                           ["uuid", self._id()]])
        return pt

    def nc(self, pt):
        self.items.append(["no_connect", ["at", g(pt[0]), g(pt[1])],
                           ["uuid", self._id()]])

    def bus_entry(self, pt, dx, dy):
        self.items.append(["bus_entry", ["at", g(pt[0]), g(pt[1])],
                           ["size", dx, dy], _stroke(),
                           ["uuid", self._id()]])
        return (g(pt[0] + dx), g(pt[1] + dy))

    # -------------------------------------------------------------- labels

    def label(self, pt, name, side="r", stub=0.0):
        """A net label at pt, reading away from it to the right ('r') or
        left ('l'), after an optional stub of wire that way."""
        x, y = g(pt[0]), g(pt[1])
        if stub:
            x2 = g(x + (stub if side == "r" else -stub))
            self.wire((x, y), (x2, y))
            if side == "l":
                x = x2
        angle, just = (0, "left bottom") if side == "r" else (
            180, "right bottom")
        if side == "l" and not stub:
            angle, just = 180, "right bottom"
        self.items.append(["label", Q(name), ["at", x, y, angle],
                           _effects(just), ["uuid", self._id()]])
        return (x, y)

    def hlabel(self, pt, name, shape="passive", side="l"):
        """A hierarchical label at pt, its text to the left or right."""
        angle, just = (180, "right") if side == "l" else (0, "left")
        self.items.append(["hierarchical_label", Q(name), ["shape", shape],
                           ["at", g(pt[0]), g(pt[1]), angle],
                           _effects(just), ["uuid", self._id()]])
        if (name, shape) not in self.hier:
            self.hier.append((name, shape))

    def text(self, x, y, s, size=1.27, justify="left bottom", bold=False):
        self.items.append(["text", Q(s), ["exclude_from_sim", "no"],
                           ["at", round(x, 3), round(y, 3), 0],
                           _effects(justify, size, bold),
                           ["uuid", self._id()]])

    def frame(self, x0, y0, x1, y1, title=None):
        """A dashed box round a block of the circuit, with its name."""
        self.items.append(["rectangle", ["start", g(x0), g(y0)],
                           ["end", g(x1), g(y1)],
                           ["stroke", ["width", 0], ["type", "dash"]],
                           ["fill", ["type", "none"]],
                           ["uuid", self._id()]])
        if title:
            self.text(x0 + 1.27, y0 - 1.0, title, 1.8, bold=True)

    def sheet_symbol(self, child, x, y, w, h, pins, page, name=None,
                     instance=0):
        """On the root: the box of a child sheet.  pins: (name, shape, side,
        offset down from the top); returns {name: (x, y)} of their ends."""
        x, y, w, h = g(x), g(y), g(w), g(h)
        if not hasattr(child, "names"):
            child.names = {}
        child.names[instance] = name or child.title
        s = ["sheet", ["at", x, y], ["size", w, h], ["exclude_from_sim", "no"],
             ["in_bom", "yes"], ["on_board", "yes"], ["dnp", "no"],
             ["stroke", ["width", 0.1524], ["type", "solid"]],
             ["fill", ["color", 0, 0, 0, 0]],
             ["uuid", Q(child.paths[instance])],
             ["property", Q("Sheetname"), Q(name or child.title),
              ["at", x, g(y - 0.7), 0], ["show_name", "no"],
              ["do_not_autoplace", "no"], _effects("left bottom")],
             ["property", Q("Sheetfile"), Q(child.filename),
              ["at", x, g(y + h + 0.7), 0], ["show_name", "no"],
              ["do_not_autoplace", "no"], _effects("left top")]]
        ends = {}
        for name_, shape, side, off in pins:
            if side in "lr":
                px, py = (x if side == "l" else x + w), g(y + off)
                angle, just = (180, "left") if side == "l" else (0, "right")
            else:               # top or bottom: offset from the left
                px, py = g(x + off), (y if side == "t" else y + h)
                angle, just = (90, "right") if side == "t" else (270, "left")
            s.append(["pin", Q(name_), shape, ["at", px, py, angle],
                      ["uuid", self._id()], _effects(just)])
            ends[name_] = (px, py)
        s.append(["instances", ["project", Q(self.d.project),
                                ["path", Q(self.d.path("")),
                                 ["page", Q(str(page))]]]])
        self.items.append(s)
        return ends

    # ---------------------------------------------------------------- file

    def auto_junctions(self):
        """A dot wherever three or more wire ends and pins meet, or an end
        or a pin lands part-way along a wire."""
        segs = [((float(i[1][1][1]), float(i[1][1][2])),
                 (float(i[1][2][1]), float(i[1][2][2])))
                for i in self.items if i[0] == "wire"]
        ends = {}
        for a, b in segs:
            for p in (a, b):
                ends[p] = ends.get(p, 0) + 1
        for inst in self.insts:
            for p in {inst.pin(num) for num in inst.pins}:
                ends[p] = ends.get(p, 0) + 1
        have = {(float(i[1][1]), float(i[1][2]))
                for i in self.items if i[0] == "junction"}
        for p, count in ends.items():
            inside = any(
                (a[0] == b[0] == p[0] and min(a[1], b[1]) < p[1]
                 < max(a[1], b[1])) or
                (a[1] == b[1] == p[1] and min(a[0], b[0]) < p[0]
                 < max(a[0], b[0])) for a, b in segs)
            if (count >= 3 or inside) and p not in have:
                self.junction(p)
                have.add(p)

    def overlaps(self):
        """Pairs of wires that run along each other: almost always two
        nets drawn on top of one another by mistake."""
        segs = [((float(i[1][1][1]), float(i[1][1][2])),
                 (float(i[1][2][1]), float(i[1][2][2])))
                for i in self.items if i[0] in ("wire", "bus")]
        bad = []
        for n, (a, b) in enumerate(segs):
            for c, e in segs[n + 1:]:
                for ax in (0, 1):
                    o = 1 - ax
                    if a[o] == b[o] == c[o] == e[o]:
                        lo = max(min(a[ax], b[ax]), min(c[ax], e[ax]))
                        hi = min(max(a[ax], b[ax]), max(c[ax], e[ax]))
                        if hi - lo > 0.01:
                            bad.append(((a, b), (c, e)))
        return bad

    def tree(self):
        self.auto_junctions()
        t = ["kicad_sch", ["version", VERSION], ["generator", Q("eeschema")],
             ["generator_version", Q("10.0")], ["uuid", Q(self.uuid)],
             ["paper", Q(self.paper)],
             ["title_block", ["title", Q(self.title)]],
             ["lib_symbols"] + list(self.libs.values())]
        order = {"junction": 0, "no_connect": 1, "bus_entry": 2, "wire": 3,
                 "bus": 4, "rectangle": 5, "text": 6, "label": 7,
                 "hierarchical_label": 9, "symbol": 10, "sheet": 11}
        t += sorted(self.items, key=lambda i: order.get(i[0], 8))
        if self.paths == [""]:
            t.append(["sheet_instances", ["path", Q("/"), ["page", Q("1")]]])
        t.append(["embedded_fonts", "no"])
        t += self.extra
        return t

    def text_out(self):
        text = dump(self.tree())
        if self.raw_tail:         # a piece of the old file, kept verbatim
            text = text[:text.rindex(")")] + "\t" + self.raw_tail + "\n)"
        return text + "\n"
