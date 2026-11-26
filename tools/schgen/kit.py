"""The idioms a schematic is drawn with: a part in line or to ground, a pad,
a supply rail on a pin, a named net on a pin, a row of decoupling."""

from . import parts
from .sch import G, Inst, g
from .sexpr import Q

P = 2.54


class Kit:
    def __init__(self, sheet):
        self.s = sheet

    # ------------------------------------------------------- two-pin parts

    def _sym(self, kind):
        return {"R": parts.R, "C": parts.C, "L": parts.L, "L_IF": parts.L_IF,
                "FB": parts.FB, "TVS": parts.TVS}[kind]

    def _fields(self, kind, value, fields):
        f = parts.passive_fields(kind, value.split(" ")[0])
        f.update(fields or {})
        return f

    def h(self, kind, a, value, fields=None, dnp=False, above=True):
        """In line, left to right from a (its pin 1); returns the far end.
        Its reference and value go above the line (or below)."""
        x, y = g(a[0]), g(a[1])
        dy = (-4.4, -2.3) if above else (2.5, 4.6)
        self.s.place(self._sym(kind), x + P, y, rot=90, value=value,
                     fields=self._fields(kind, value, fields), dnp=dnp,
                     ref_at=(0, dy[0]), val_at=(0, dy[1]), justify=None)
        return (g(x + 2 * P), y)

    def v(self, kind, a, value, fields=None, dnp=False, up=False,
          left=False):
        """Down from a (or up from it); returns the far end."""
        x, y = g(a[0]), g(a[1])
        cy = y - P if up else y + P
        tx = -1.9 if left else 1.9
        self.s.place(self._sym(kind), x, cy, value=value,
                     fields=self._fields(kind, value, fields), dnp=dnp,
                     ref_at=(tx, -1.1), val_at=(tx, 1.2),
                     justify="right" if left else "left")
        return (x, g(y - 2 * P) if up else g(y + 2 * P))

    def shunt(self, kind, a, value, net="GND", **kw):
        """From a down to ground."""
        end = self.v(kind, a, value, **kw)
        self.gnd(end)
        return a

    def pull(self, kind, a, value, net, **kw):
        """From a up to a supply rail."""
        end = self.v(kind, a, value, up=True, **kw)
        self.rail(end, net)
        return a

    def pad(self, a, db):
        """A pi attenuator in line; returns its far end."""
        shunt, series = {3: ("294R", "17R4"), 6: ("150R", "37R4"),
                         2: ("432R", "11R5"), 10: ("95R3", "71R5")}[db]
        x, y = g(a[0]), g(a[1])
        self.s.wire(a, (x + 3 * P, y))
        self.shunt("R", (x + P, y), shunt)
        self.s.junction((x + P, y))
        b = self.h("R", (x + 3 * P, y), series)
        self.s.wire(b, (x + 8 * P, y))
        self.shunt("R", (x + 7 * P, y), shunt)
        self.s.junction((x + 7 * P, y))
        self.s.text(x + 5 * P, y - 8.3, "%d dB" % db, justify="bottom")
        return (g(x + 8 * P), y)

    # ------------------------------------------------------ rails and nets

    def gnd(self, pt):
        self.s.place(parts.GND, pt[0], pt[1], value="GND",
                     val_at=(0, 3.3), justify=None, show_value=False)

    def rail(self, pt, net):
        self.s.place(parts.VCC, pt[0], pt[1], value=net, val_at=(0, -3.6),
                     justify=None)

    def flag(self, pt):
        self.s.place(parts.PWR_FLAG, pt[0], pt[1], val_at=(0, -4.6),
                     justify=None, show_value=False)

    def vdd(self, inst, pin, net, rise=P):
        """A rail on a pin that points up."""
        a = inst.pin(pin)
        b = self.s.wire(a, (a[0], a[1] - rise))
        self.rail(b, net)
        return b

    def vss(self, inst, *pins, drop=P):
        """Ground on pins that point down; several share one symbol."""
        pts = sorted(inst.pin(p) for p in pins)
        y = g(pts[0][1] + drop)
        for a in pts:
            self.s.wire(a, (a[0], y))
        if len(pts) > 1:
            self.s.wire((pts[0][0], y), (pts[-1][0], y))
            for a in pts[1:-1]:
                self.s.junction((a[0], y))
        self.gnd((pts[0][0], y))

    def net(self, inst, pin, name, stub=None):
        """A named net on a pin, the name written along a stub of wire."""
        a = inst.pin(pin)
        side = inst.side(pin)
        return self.name(a, name, side, stub)

    def name(self, a, name, side="r", stub=None):
        """A stub of wire from a, to the left or right, with a net name
        along it; returns its far end."""
        plain = name.replace("~{", "").replace("}", "")
        n = stub or max(3, int((len(plain) * 1.05 + 1.5) / G) + 1) * G
        x, y = g(a[0]), g(a[1])
        b = (g(x - n), y) if side == "l" else (g(x + n), y)
        self.s.wire(a, b)
        # the name sits at the free end, reading back along the stub
        angle, just = (0, "left") if side == "l" else (180, "right")
        self.s.items.append(["label", Q(name), ["at", b[0], b[1], angle],
                             ["effects", ["font", ["size", 1.27, 1.27]],
                              ["justify", just, "bottom"]],
                             ["uuid", self.s._id()]])
        return b

    def port(self, a, name, shape="passive", side="l", run=0.0):
        """A hierarchical label after a run of wire from a."""
        b = (g(a[0] + (-run if side == "l" else run)), g(a[1]))
        if run:
            self.s.wire(a, b)
        self.s.hlabel(b, name, shape, side)
        return b

    # ----------------------------------------------------------------- ICs

    def ic(self, sym, pin, pt, mirror=False, rot=0, **kw):
        """Place a symbol so that this pin of it lands on pt."""
        probe = Inst(self.s, sym, 0.0, 0.0, rot, mirror)
        px, py = probe.pin(pin)
        return self.s.place(sym, pt[0] - px, pt[1] - py, rot=rot,
                            mirror=mirror, **kw)

    def switch(self, pt, ctrl, mirror=False, rail="+3V3_RF"):
        """A PE42520 with its common pin on pt; RF1 is the upper throw
        (CTRL high), RF2 the lower."""
        u = self.ic(parts.PE42520, "RFC", pt, mirror=mirror)
        self.vdd(u, "VDD", rail)
        self.vss(u, "LS", "VSS", "GND")
        self.net(u, "CTRL", ctrl)
        return u

    def decoupling(self, x, y, rows, title="Supply decoupling"):
        """Rows of (rail, [(value, what it is for), ...]): the capacitors
        that sit at the supply pins, drawn together."""
        x, y = g(x), g(y)
        width = max(len(caps) for _, caps in rows) * 4 * P + 8 * P
        self.s.frame(x - 2 * P, y - 5 * P, x + width,
                     y + (len(rows) - 1) * 10 * P + 6 * P, title)
        for i, (net, caps) in enumerate(rows):
            yy = g(y + i * 10 * P)
            self.rail((x, yy), net)
            end = (g(x + len(caps) * 4 * P), yy)
            self.s.wire((x, yy), end)
            for k, (value, what) in enumerate(caps):
                a = (g(x + (k + 1) * 4 * P), yy)
                self.shunt("C", a, value)
                if k < len(caps) - 1:
                    self.s.junction(a)
                self.s.text(a[0] + 1.9, yy + 2 * P + 2.2, what, 1.0,
                            "left top")

    def ladder(self, a, parts_, lead=P):
        """A ladder from a, left to right.  ("C", value) is a shunt to
        ground at the present node and ("L", value) a part in line;
        ("s", kind, value) and ("p", kind, value) say in line or to ground
        outright; ("L", value, "C", value) is an inductor in line with a
        capacitor across it.  Returns the far end."""
        x, y = g(a[0]), g(a[1])
        for item in parts_:
            if len(item) == 2:
                item = ("p" if item[0] == "C" else "s",) + tuple(item)
            if len(item) == 3 and item[0] == "p":
                self.shunt(item[1], (x, y), item[2])
                self.s.junction((x, y))
            elif len(item) == 3:
                self.s.wire((x, y), (x + lead, y))
                end = self.h(item[1], (x + lead, y), item[2])
                self.s.wire(end, (end[0] + lead, y))
                x = g(end[0] + lead)
            else:
                self.s.wire((x, y), (x + lead, y))
                end = self.h(item[0], (x + lead, y), item[1])
                self.s.wire(end, (end[0] + lead, y))
                top = g(y - 4 * P)
                self.s.wire((x, y), (x, top), (x + lead, top))
                e2 = self.h(item[2], (x + lead, top), item[3])
                self.s.wire(e2, (end[0] + lead, top), (end[0] + lead, y))
                self.s.junction((x, y))
                x = g(end[0] + lead)
                self.s.junction((x, y))
        return (x, y)

    def breakout(self, pt, bus, members, shape="input", side="l"):
        """A bus arriving at a hierarchical label on the sheet's edge,
        broken out into its named members.  Elsewhere on the sheet the
        members are met by name."""
        prefix = bus.split("{")[0].split("[")[0]
        x, y = g(pt[0]), g(pt[1])
        self.s.hlabel((x, y), bus, shape, side)
        sign = 1 if side == "l" else -1
        bx = g(x + sign * 2 * P)
        self.s.wire((x, y), (bx, y), (bx, y + len(members) * P), bus=True)
        for i, m in enumerate(members):
            a = self.s.bus_entry((bx, y + i * P), sign * P, P)
            self.name(a, "%s.%s" % (prefix, m) if "{" in bus else m,
                      "r" if side == "l" else "l")

    def pma3(self, a, rail="+5V_RF"):
        """A PMA3-83LN+ stage from a: block, input inductor, the amplifier,
        feed inductor to the supply, block.  Returns (far end, amplifier)."""
        x, y = g(a[0]), g(a[1])
        b = self.h("C", (x, y), "100pF")
        n = self.s.wire(b, (b[0] + 2 * P, y))
        self.shunt("L", n, "TBD")
        self.s.junction(n)
        u = self.ic(parts.PMA3_83LN, "RF-IN", (n[0] + 5 * P, y))
        self.s.wire(n, u.pin("RF-IN"))
        self.vss(u, "GND")
        o = u.pin("RF-OUT")
        m = self.s.wire(o, (o[0] + 3 * P, y))
        self.pull("L", m, "TBD", rail)
        self.s.junction(m)
        self.s.wire(m, (m[0] + 3 * P, y))
        end = self.h("C", (m[0] + 3 * P, y), "100pF")
        return end, u

    def ldo(self, x, y, sym, out, source="VBUS_F", flag=True):
        """A linear regulator cell at x, y: source rail in, out rail out."""
        u = self.s.place(sym, x, y)
        i, o = u.pin("IN"), u.pin("OUT")
        a = self.s.wire(i, (i[0] - 4 * P, i[1]))
        self.shunt("C", a, "1uF", left=True)
        self.pull_wire(a, source)
        en = u.pin("EN")
        self.s.wire(en, (en[0] - P, en[1]), (en[0] - P, i[1]))
        self.s.junction((en[0] - P, i[1]))
        self.vss(u, "GND")
        self.s.nc(u.pin("NC"))
        b = self.s.wire(o, (o[0] + 4 * P, o[1]))
        self.shunt("C", b, "1uF")
        c = self.s.wire(b, (b[0] + 3 * P, b[1]))
        self.s.junction(b)
        self.pull_wire(c, out)
        if flag:
            self.flag((b[0] + P, b[1]))
            self.s.junction((b[0] + P, b[1]))
        return u

    def pull_wire(self, a, net, rise=P):
        b = self.s.wire(a, (a[0], a[1] - rise))
        self.rail(b, net)
        return b
