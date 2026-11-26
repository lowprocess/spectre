"""The 6.4 GHz proposal (sim/README.md) as a KiCad schematic: one function a
sheet.  Signals run left to right, supplies come from above, ground goes
below, controls arrive by name."""

from . import parts
from .kit import Kit, P
from .sch import NS, Design, Sheet, g


def UUID5(name):
    import uuid
    return uuid.uuid5(NS, name)

ROOT = "e2b3a745-ca2b-407e-8017-842114c52164"
# the sheets the project already had keep their identities
UU = {"rf_input": "d29017c7-873c-498f-bde0-2c20a1aea9c3",
      "fe_low": "266613fc-9a6e-4dca-94e3-c0ce67d05966",
      "if_1": "bf6ae323-e177-4643-87bd-72d3f873e10e",
      "if_2": "b5716b66-1d83-49ac-b649-32aca3372ac7",
      "adc": "76c18ca0-2499-4c2a-ba50-9a0ecf1ebc8b",
      "controller": "78ee1970-58a4-43e5-8613-0c075940edd5",
      "lo1": "bfad2d43-1850-494b-b6df-f5acbe5279ae",
      "lo2": "e8db61a9-ea8d-4997-90db-6d7c76c362cb"}

ALIASES = {"SYN_CTRL": ["SCK", "MUX", "SDI", "~{CS}", "CE", "RC", "RD"],
           "IN_CTRL": ["SCK", "SDI", "LE", "V1", "V2"],
           "FE_CTRL": ["SEL_1", "PRE_BYP"],
           "IF_CTRL": ["SCK", "SDI", "LE", "SEL_MIX"],
           "ADC_CTRL": ["~{CS}", "SCK", "SDIO"]}


def rf_input(d):
    s = Sheet(d, "rf_input.kicad_sch", "RF input: protection, attenuator, "
              "band select", paper="A4", base=100, paths=[UU["rf_input"]])
    k = Kit(s)
    y = 73.66
    s.text(20.32, 25.4, "RF INPUT", 3.0, bold=True)
    s.text(20.32, 31.75, "0.1 MHz to 6.4 GHz, 50 ohm.  Up to +20 dBm with "
           "the attenuator at 30 dB; never DC beyond 25 V.", 1.5)

    j = k.ic(parts.SMA, "In", (40.64, y), mirror=True, ref="J",
             value="SMA", val_at=(0, -5.5), ref_at=(0, -7.6), justify=None,
             fields={"Footprint": "Connector_Coaxial:SMA_Amphenol_132289_"
                     "EdgeMount", "PartNumber": "132289",
                     "Manufacturer": "Amphenol RF"})
    k.gnd(s.wire(j.pin("Ext"), (j.pin("Ext")[0], y + 3 * P)))
    a = s.wire(j.pin("In"), (48.26, y))
    b = k.h("C", a, "100nF", fields={"PartNumber": "550L104KTT",
                                     "Manufacturer": "Kyocera AVX", "IPN": "",
                                     "Voltage": "16V"})
    s.text(a[0] + P, y + 4.5, "DC block\n16 kHz to 40 GHz", 1.0, "top")
    n = s.wire(b, (b[0] + 5 * P, y))
    k.shunt("TVS", n, "ESD131-B1-W0201")
    s.junction(n)

    att = k.ic(parts.PE43704, "RF1", (104.14, y))
    s.wire(n, att.pin("RF1"))
    v = k.vdd(att, "VDD", "+3V3_RF")
    ps = att.pin("P/~{S}")
    s.wire(ps, (ps[0], v[1]), v)
    k.vss(att, "A0-A2", "C0.25-C16", "VSS", "GND")
    k.net(att, "SI", "RFIN.SDI")
    k.net(att, "CLK", "RFIN.SCK")
    k.net(att, "LE", "RFIN.LE")
    s.text(att.x, att.y + 29.5, "Input attenuator, 0 to 31.75 dB\n"
           "serial mode, address 000", 1.0, "top")

    sw = k.ic(parts.PE42540, "RFC", (165.1, y))
    s.wire(att.pin("RF2"), sw.pin("RFC"))
    k.vdd(sw, "VDD", "+3V3_RF")
    k.vss(sw, "VSS", "GND")
    k.net(sw, "V1", "RFIN.V1")
    k.net(sw, "V2", "RFIN.V2")
    s.text(sw.x, sw.y + 27.0, "Band select\nV2 V1:  00 RF1,  01 RF2,  "
           "10 RF3,  11 RF4", 1.0, "top")

    xr = 256.54
    for pin, name, what in (("RF1", "RF_L1", "15 MHz to 2.29 GHz"),
                            ("RF2", "RF_L2", "2.29 to 3.0 GHz"),
                            ("RF3", "RF_HIGH", "3.0 to 6.4 GHz")):
        p = sw.pin(pin)
        k.port(p, name, "output", "r", run=xr - p[0])
        s.text(xr - 8 * P, p[1] - 0.8, what, 1.0, "right bottom")
    p = sw.pin("RF4")
    yd = g(y + 14 * P)
    a = s.wire(p, (p[0] + 2 * P, p[1]), (p[0] + 2 * P, yd),
               (p[0] + 4 * P, yd))
    b = k.ladder(a, [("C", "120pF"), ("L", "390nH"), ("C", "220pF"),
                     ("L", "390nH"), ("C", "120pF")], lead=3 * P)
    k.port(b, "IF_DIRECT", "output", "r", run=xr - b[0])
    s.frame(a[0] - P, yd - 4 * P, b[0] + 4 * P, yd + 5 * P,
            "Direct path low-pass, 30 MHz")
    s.text(xr - P, yd - 0.8, "0.1 to 15 MHz", 1.0, "right bottom")

    k.breakout((25.4, 134.62), "RFIN{IN_CTRL}",
               ["SCK", "SDI", "LE", "V1", "V2"])
    k.decoupling(101.6, 152.4, [("+3V3_RF", [("100nF", "U100"),
                                              ("100pF", "U100"),
                                              ("100nF", "U101"),
                                              ("100pF", "U101")])])
    return s




FP = "spectre_filters:"          # the printed filters, as footprints


def _filter(k, sym, pt, value, footprint):
    """A printed filter with its first pin on pt; returns its far pin."""
    u = k.ic(sym, "1", pt, value=value,
             fields={"Footprint": FP + footprint, "PartNumber": footprint,
                     "Manufacturer": "PCB"})
    if "GND" in u.names:
        k.vss(u, "GND")
    return u.pin("2")


def _bypassed(k, s, a, ctrl, stage):
    """Two switches round a stage: the lower throws through
    stage(point) -> far point, the upper throws joined by a line that
    passes over it.  Returns the far common pin."""
    u1 = k.switch(a, ctrl)
    e = stage(s.wire(u1.pin("RF2"), (u1.pin("RF2")[0] + 4 * P,
                                     u1.pin("RF2")[1])))
    u2 = k.switch((e[0] + 4 * P + 20.32, a[1]), ctrl, mirror=True)
    s.wire(e, u2.pin("RF2"))
    p1, p2 = u1.pin("RF1"), u2.pin("RF1")
    top = g(p1[1] - 9 * P)
    s.wire(p1, (p1[0] + 2 * P, p1[1]), (p1[0] + 2 * P, top),
           (p2[0] - 2 * P, top), (p2[0] - 2 * P, p2[1]), p2)
    s.text((p1[0] + p2[0]) / 2, top - 1.0, "bypass", 1.2, "bottom")
    return u2.pin("RFC")


def fe_low(d):
    s = Sheet(d, "fe_low.kicad_sch", "Low band front end: preselection, "
              "preamplifier", paper="A3", base=200, paths=[UU["fe_low"]])
    k = Kit(s)
    s.text(20.32, 25.4, "LOW BAND FRONT END", 3.0, bold=True)
    s.text(20.32, 31.75, "15 MHz to 3.0 GHz in two preselected ranges, "
           "then the image low-pass and a switched preamplifier.", 1.5)
    ya, yb = 76.2, 111.76
    a = k.port((30.48, ya), "RF_L1", "input", "l")
    f1 = k.ic(parts.LFCN, "IN", (55.88, ya), val_at=(0, -6.0),
              ref_at=(0, -8.1), justify=None)
    s.wire(a, f1.pin("IN"))
    k.gnd(f1.pin("GND"))
    f2 = k.ic(parts.LFCN, "IN", (88.9, ya), val_at=(0, -6.0),
              ref_at=(0, -8.1), justify=None)
    s.wire(f1.pin("OUT"), f2.pin("IN"))
    k.gnd(f2.pin("GND"))
    s.text(82.55, ya - 12.0, "L1: 15 MHz to 2.29 GHz\ntwo low-passes, 2.25 "
           "GHz", 1.2, "bottom")

    b = k.port((30.48, yb), "RF_L2", "input", "l")
    e = _filter(k, parts.FILTER_BP_G, s.wire(b, (68.58, yb)),
                "BPF 2.3-3.0 GHz", "l2_bpf_2g3_3g0_interdigital")
    s.text(76.2, yb - 12.5, "L2: 2.29 to 3.0 GHz\nprinted interdigital "
           "band-pass", 1.2, "bottom")

    sw = k.switch((149.86, ya + P), "FEL.SEL_1", mirror=True)
    s.wire(f2.pin("OUT"), sw.pin("RF1"))
    r2 = sw.pin("RF2")
    s.wire(e, (r2[0] - 4 * P, yb), (r2[0] - 4 * P, r2[1]), r2)
    c = sw.pin("RFC")
    e = _filter(k, parts.FILTER_LP, s.wire(c, (c[0] + 10 * P, c[1])),
                "LPF 4.0 GHz", "if1_lpf_4g0_radial")
    s.text(e[0] - 8.9, c[1] - 9.5, "keeps the image band\n(6.8 to 9.8 GHz) "
           "off the mixer", 1.2, "bottom")

    def amp(p):
        q = k.h("C", s.wire(p, (p[0] + P, p[1])), "10nF")
        u = k.ic(parts.TRF37D73, "RFIN", (q[0] + 8 * P, p[1]))
        s.wire(q, u.pin("RFIN"))
        k.vdd(u, "VCC", "+3V3_RF")
        k.vss(u, "GND")
        k.net(u, "PWDN", "FEL.PRE_BYP")
        o = u.pin("RFOUT")
        m = s.wire(o, (o[0] + 3 * P, o[1]))
        k.pull("L", m, "1uH", "+3V3_RF",
               fields={"PartNumber": "0402DF-102XJR",
                       "Manufacturer": "Coilcraft"})
        return k.h("C", s.wire(m, (m[0] + 4 * P, m[1])), "10nF")

    out = _bypassed(k, s, s.wire(e, (e[0] + 10 * P, e[1])), "FEL.PRE_BYP",
                    amp)
    k.port(out, "RF_LOW", "output", "r", run=6 * P)
    s.text(e[0] + 60, c[1] + 24.0, "Preamplifier, 20 dB, NF 1.6 dB; "
           "bypassed and powered down when FEL.PRE_BYP is high", 1.2,
           "top")
    s.text(20.32, 150.0, "FEL.SEL_1 high: L1.  Low: L2.", 1.2)
    k.breakout((30.48, 160.02), "FEL{FE_CTRL}", ["SEL_1", "PRE_BYP"])
    k.decoupling(127.0, 190.5, [("+3V3_RF", [
        ("100nF", "U200"), ("100nF", "U201"), ("100nF", "U202"),
        ("100nF", "U203"), ("1nF", "U202"), ("100nF", "L200")])])
    return s


def fe_high(d):
    s = Sheet(d, "fe_high.kicad_sch", "High band front end: preselection, "
              "preamplifier", paper="A3", base=300)
    k = Kit(s)
    s.text(20.32, 25.4, "HIGH BAND FRONT END", 3.0, bold=True)
    s.text(20.32, 31.75, "3.0 to 6.4 GHz, converted straight to the 12 MHz "
           "IF by the second mixer.  Each range has a band-pass and a "
           "low-pass.", 1.5)
    y = 96.52
    a = k.port((30.48, y), "RF_HIGH", "input", "l")
    s1 = k.switch((55.88, y), "FEH.SEL_1")
    s.wire(a, s1.pin("RFC"))
    ya, yb = y - 8 * P, y + 12 * P
    rows = []
    for pin, yy, bp, bpf, lp, lpf, what in (
            ("RF1", ya, "BPF 2.9-4.5 GHz", "h1_bpf_3g0_4g5_stub",
             "LPF 5.0 GHz", "h1_lpf_5g0_radial", "H1: 3.0 to 4.4 GHz"),
            ("RF2", yb, "BPF 4.3-6.4 GHz", "h2_bpf_4g3_6g4_stub",
             "LPF 7.0 GHz", "h2_lpf_7g0_radial", "H2: 4.4 to 6.4 GHz")):
        p = s1.pin(pin)
        q = s.wire(p, (p[0] + 3 * P, p[1]), (p[0] + 3 * P, yy),
                   (p[0] + 8 * P, yy))
        e = _filter(k, parts.FILTER_BP_G, q, bp, bpf)
        e = _filter(k, parts.FILTER_LP, s.wire(e, (e[0] + 8 * P, yy)), lp,
                    lpf)
        s.text(q[0] + 24, yy - 9.5, what, 1.2, "bottom")
        rows.append(e)
    s2 = k.switch((rows[0][0] + 16 * P, y), "FEH.SEL_1", mirror=True)
    for e, pin in zip(rows, ("RF1", "RF2")):
        p = s2.pin(pin)
        s.wire(e, (p[0] - 3 * P, e[1]), (p[0] - 3 * P, p[1]), p)

    def amp(p):
        return k.pma3(s.wire(p, (p[0] + P, p[1])))[0]

    c = s2.pin("RFC")
    out = _bypassed(k, s, s.wire(c, (c[0] + 18 * P, c[1])), "FEH.PRE_BYP",
                    amp)
    k.port(out, "RF_HIGH_OUT", "output", "r", run=6 * P)
    s.text(c[0] + 50, y + 24.0, "Preamplifier, 21 dB, NF 1.3 dB; bypassed "
           "when FEH.PRE_BYP is high", 1.2, "top")
    s.text(20.32, 160.0, "FEH.SEL_1 high: H1.  Low: H2.\n"
           "L (TBD): the PMA3-83LN+ data sheet's input and feed inductors.",
           1.2)
    k.breakout((30.48, 175.26), "FEH{FE_CTRL}", ["SEL_1", "PRE_BYP"])
    k.decoupling(127.0, 200.66, [
        ("+3V3_RF", [("100nF", "U300"), ("100nF", "U301"), ("100nF", "U302"),
                     ("100nF", "U304")]),
        ("+5V_RF", [("100nF", "L301"), ("100pF", "L301"), ("10uF", "")])])
    return s


def lo_drive(d):
    s = Sheet(d, "lo_drive.kicad_sch", "LO drive: buffer to +7 dBm",
              paper="A4", bases=[500, 550],
              paths=[str(UUID5("lo_drive/1")), str(UUID5("lo_drive/2"))])
    k = Kit(s)
    s.text(20.32, 25.4, "LO DRIVE", 3.0, bold=True)
    s.text(20.32, 31.75, "One output of the synthesizer, padded, buffered "
           "and padded again: +7 dBm for the mixer, 3 to 6.4 GHz.\nThe "
           "other output ends in 50 ohm.  Used twice: LO1 and LO2.", 1.5)
    y = 86.36
    k.breakout((30.48, y + 12 * P), "LO{P N}", ["P", "N"], shape="input")
    p = (63.5, y)
    k.name(p, "LO.P", "l")
    n = (63.5, y + 12 * P)
    k.name(n, "LO.N", "l")
    r = k.h("R", n, "49R9")
    k.gnd(s.wire(r, (r[0] + P, r[1]), (r[0] + P, r[1] + P)))
    s.text(n[0] + 14.0, n[1] + 1.0, "the unused output, terminated", 1.2,
           "left")
    e = k.pad(s.wire(p, (p[0] + 4 * P, y)), 3)
    e, u = k.pma3(s.wire(e, (e[0] + 5 * P, y)))
    s.text(u.x, y - 14.0, "buffer, 21 dB", 1.2, "bottom")
    e = k.pad(s.wire(e, (e[0] + 5 * P, y)), 3)
    k.port(e, "LO_OUT", "output", "r", run=8 * P)
    s.text(20.32, 150.0, "L (TBD): the PMA3-83LN+ data sheet's input and "
           "feed inductors.\nThe pads set the level and give the mixer "
           "and the synthesizer a 50 ohm face; trim them to the "
           "synthesizer's output power.", 1.2)
    k.decoupling(134.62, 165.1, [("+5V_RF", [
        ("100nF", "L501"), ("100pF", "L501"), ("10uF", "")])])
    return s


def if_1(d):
    s = Sheet(d, "if_1.kicad_sch", "First IF: two mixers, 3.4 GHz IF filter",
              paper="A3", base=400, paths=[UU["if_1"]])
    k = Kit(s)
    s.text(20.32, 25.4, "FIRST IF", 3.0, bold=True)
    s.text(20.32, 31.75, "Low band: up to 3.4 GHz (LO1 = f + 3.4 GHz), "
           "filtered, then down to 12 MHz (LO2 = 3.388 or 3.402 GHz).\n"
           "High band: straight into the second mixer (LO2 = f +/- 12 MHz).",
           1.5)
    y, ylo = 111.76, 180.34
    sim = {"Value": "SIM-83+"}
    a = k.port((27.94, y), "RF_LOW", "input", "l")
    e = k.pad(s.wire(a, (a[0] + 3 * P, y)), 3)
    m1 = k.ic(parts.SIM83, "IF", (e[0] + 5 * P, y), fields=sim,
              ref_at=(0, -12.0), val_at=(0, -9.9), justify=None)
    s.wire(e, m1.pin("IF"))
    gp = m1.pin("GND")
    k.gnd(s.wire(gp, (gp[0] - P, gp[1]), (gp[0] - P, gp[1] + 2 * P)))
    s.text(m1.x, y - 17.0, "MIX1\n0.015-3.0 GHz in on IF\n3.4 GHz out on "
           "RF", 1.2, "bottom")
    lo = m1.pin("LO")
    k.port(s.wire(lo, (lo[0] + 2 * P, lo[1]), (lo[0] + 2 * P, ylo),
                  (27.94, ylo)), "LO1", "input", "l")
    s.text(30.48, ylo - 1.0, "3.415 to 6.4 GHz, +7 dBm", 1.2)
    o = m1.pin("RF")
    e, u = k.pma3(s.wire(o, (o[0] + 4 * P, y)))
    s.text(u.x, y - 12.5, "IF1 amplifier, 21 dB", 1.2, "bottom")
    e = k.pad(s.wire(e, (e[0] + 3 * P, y)), 6)
    e = _filter(k, parts.FILTER_LP, s.wire(e, (e[0] + 4 * P, y)),
                "LPF 4.0 GHz", "if1_lpf_4g0_radial")
    e = _filter(k, parts.FILTER_BP, s.wire(e, (e[0] + 5 * P, y)),
                "BPF 3.4 GHz", "if1_bpf_3g4_hairpin")
    s.text(e[0] - 8.9, y - 9.5, "5 pole hairpin\n3.34 to 3.46 GHz", 1.2,
           "bottom")
    sw = k.switch((e[0] + 13 * P, y - P), "SEL_HIGH", mirror=True)
    s.wire(e, sw.pin("RF2"))
    hi = k.port((27.94, y - 22 * P), "RF_HIGH", "input", "l")
    r1 = sw.pin("RF1")
    s.wire(hi, (r1[0] - 3 * P, hi[1]), (r1[0] - 3 * P, r1[1]), r1)
    s.text(30.48, hi[1] - 1.0, "high band, 3.0 to 6.4 GHz, from its front "
           "end", 1.2)
    c = sw.pin("RFC")
    m2 = k.ic(parts.SIM83, "RF", (c[0] + 12 * P, c[1]), mirror=True,
              fields=sim, ref_at=(0, -12.0), val_at=(0, -9.9), justify=None)
    s.wire(c, m2.pin("RF"))
    gp = m2.pin("GND")
    k.gnd(s.wire(gp, (gp[0] + P, gp[1]), (gp[0] + P, gp[1] + 2 * P)))
    s.text(m2.x, c[1] - 17.0, "MIX2\n3.0-6.4 GHz in on RF\n12 MHz out on "
           "IF", 1.2, "bottom")
    lo = m2.pin("LO")
    lx = lo[0] - 3 * P
    s.wire(lo, (lx, lo[1]), (lx, ylo + 4 * P), (27.94, ylo + 4 * P))
    k.port((27.94, ylo + 4 * P), "LO2", "input", "l")
    s.text(30.48, ylo + 4 * P - 1.0, "2.988 to 6.412 GHz, +7 dBm", 1.2)
    o = m2.pin("IF")
    n = s.wire(o, (o[0] + 4 * P, o[1]))
    e = k.ladder(n, [("s", "L_IF", "390nH"), ("p", "C", "150pF"),
                     ("s", "L_IF", "130nH")], lead=2 * P)
    k.port(e, "IF_MIX", "output", "r", run=3 * P)
    t = s.wire(n, (n[0], n[1] + 10 * P), (n[0] + 2 * P, n[1] + 10 * P))
    k.ladder(t, [("s", "C", "68pF"), ("p", "L_IF", "200nH"),
                 ("s", "C", "220pF"), ("p", "R", "49R9")], lead=2 * P)
    s.frame(n[0] - P, n[1] - 5 * P, e[0] + P, n[1] + 16 * P,
            "Diplexer, 30 MHz")
    s.text(n[0] - P, n[1] + 18 * P, "below 30 MHz: on to the IF\nabove: "
           "into 50 ohm", 1.2, "top")
    q = k.name(k.port((27.94, ylo + 12 * P), "SEL_HIGH", "input", "l"),
               "SEL_HIGH", "r")
    s.text(20.32, ylo + 16 * P, "SEL_HIGH high: the second mixer takes the "
           "high band.  Low: the first IF.\nL (TBD): the PMA3-83LN+ data "
           "sheet's input and feed inductors.", 1.2)
    k.decoupling(190.5, ylo + 18 * P, [
        ("+5V_RF", [("100nF", "L401"), ("100pF", "L401"), ("10uF", "")]),
        ("+3V3_RF", [("100nF", "U402"), ("100pF", "U402")])])
    return s


def _gain_stage(k, s, a, rail="+5V_A"):
    """An LMH6629 as a 50 ohm gain block: 49.9 ohm to the mid-supply at
    its input, gain of 40 (32 dB).  From a (after a blocking capacitor);
    returns its output."""
    k.pull("R", a, "49R9", "VMID")
    u = k.ic(parts.LMH6629, "+", (a[0] + 6 * P, a[1]))
    s.wire(a, u.pin("+"))
    k.vdd(u, "V+", rail)
    k.vss(u, "V-")
    o = u.pin("1")
    m = u.pin("-")
    yf = g(o[1] + 7 * P)
    fb = (g(m[0] - 2 * P), yf)
    s.wire(m, (fb[0], m[1]), fb)
    e = k.h("R", s.wire(fb, (fb[0] + 5 * P, yf)), "499R", above=False)
    q = s.wire(o, (o[0] + 2 * P, o[1]))
    s.wire(e, (q[0], yf), q)
    b = k.v("R", fb, "12R7", left=True)
    k.shunt("C", b, "1uF", left=True)
    return q, u


def if_2(d):
    s = Sheet(d, "if_2.kicad_sch", "Second IF: gain, attenuator, "
              "anti-alias filter", paper="A3", base=600, paths=[UU["if_2"]])
    k = Kit(s)
    s.text(20.32, 25.4, "SECOND IF", 3.0, bold=True)
    s.text(20.32, 31.75, "12 MHz IF (7 to 17 MHz used) from the second "
           "mixer, or 0.1 to 15 MHz straight from the input.  58 dB of "
           "gain less the attenuator, in 50 ohm.", 1.5)
    y = 93.98
    sw = k.switch((76.2, y), "IF.SEL_MIX", mirror=True)
    a = k.port((30.48, sw.pin("RF1")[1] - 4 * P), "IF_MIX", "input", "l")
    p = sw.pin("RF1")
    s.wire(a, (p[0] - 3 * P, a[1]), (p[0] - 3 * P, p[1]), p)
    b = k.port((30.48, sw.pin("RF2")[1] + 8 * P), "IF_DIRECT", "input", "l")
    p = sw.pin("RF2")
    s.wire(b, (p[0] - 3 * P, b[1]), (p[0] - 3 * P, p[1]), p)
    c = sw.pin("RFC")
    e = k.h("C", s.wire(c, (c[0] + 8 * P, y)), "1uF")
    q, u1 = _gain_stage(k, s, s.wire(e, (e[0] + 3 * P, y)))
    s.text(u1.x, y - 17.0, "32 dB; 26 dB into 50 ohm", 1.2, "bottom")
    e = k.h("C", s.wire(q, (q[0] + P, q[1])), "1uF")
    e = k.h("R", s.wire(e, (e[0] + 2 * P, e[1])), "49R9")
    y = e[1]
    att = k.ic(parts.PE43711, "RF1", (e[0] + 14 * P, y))
    s.wire(e, att.pin("RF1"))
    v = k.vdd(att, "VDD", "+3V3_RF")
    ps = att.pin("P/~{S}")
    s.wire(ps, (ps[0], v[1]), v)
    k.vss(att, "C0.25-C16", "GND")
    k.net(att, "SI", "IF.SDI")
    k.net(att, "CLK", "IF.SCK")
    k.net(att, "LE", "IF.LE")
    s.text(att.x, att.y + 27.0, "IF attenuator, 0 to 31.75 dB\nserial "
           "mode", 1.2, "top")
    o = att.pin("RF2")
    n = s.wire(o, (o[0] + 6 * P, y))
    e = k.ladder(n, [("C", "130pF"), ("L_IF", "470nH", "C", "75pF"),
                     ("C", "240pF"), ("L_IF", "470nH", "C", "110pF"),
                     ("C", "220pF"), ("L_IF", "330nH", "C", "180pF"),
                     ("C", "300pF"), ("L_IF", "560nH", "C", "24pF"),
                     ("C", "180pF")], lead=2 * P)
    s.frame(n[0] - 2 * P, y - 9 * P, e[0] + 5 * P, y + 6 * P,
            "Anti-alias low-pass: 9th order elliptic, 17.5 MHz, 70 dB "
            "from 21.5 MHz")
    e = k.h("C", s.wire(e, (e[0] + 7 * P, y)), "1uF")
    q, u2 = _gain_stage(k, s, s.wire(e, (e[0] + 3 * P, y)))
    s.text(u2.x, y - 17.0, "32 dB", 1.2, "bottom")
    k.port(q, "IF_AMP", "output", "r", run=4 * P)

    yb = 182.88
    k.breakout((30.48, yb), "IF{IF_CTRL}", ["SCK", "SDI", "LE", "SEL_MIX"])
    s.text(20.32, yb + 20.0, "IF.SEL_MIX high: the second mixer.  Low: the "
           "direct path.\nBoth amplifiers idle at VMID; their feedback "
           "returns through 1 uF, so DC gain is 1.", 1.2)
    x0 = 111.76
    s.frame(x0 - 4 * P, yb - 6 * P, x0 + 16 * P, yb + 11 * P,
            "Mid-supply, 2.5 V")
    t = k.pull("R", (x0, yb), "1k", "+5V_A")
    k.shunt("R", (x0, yb), "1k")
    m = s.wire((x0, yb), (x0 + 4 * P, yb))
    k.shunt("C", m, "10uF")
    m = s.wire(m, (m[0] + 4 * P, yb))
    k.shunt("C", m, "100nF")
    m = s.wire(m, (m[0] + 4 * P, yb))
    k.pull_wire(m, "VMID")
    k.flag((m[0] - 2 * P, yb))
    k.decoupling(190.5, yb + 5.08, [
        ("+5V_A", [("100nF", "U601"), ("10nF", "U601"), ("100nF", "U603"),
                   ("10nF", "U603"), ("10uF", "")]),
        ("+3V3_RF", [("100nF", "U600"), ("100nF", "U602"),
                     ("100pF", "U602")])])
    return s


def adc(d):
    s = Sheet(d, "adc.kicad_sch", "ADC driver, ADC, 40 MHz clock",
              paper="A3", base=700, paths=[UU["adc"]])
    k = Kit(s)
    s.text(20.32, 25.4, "DRIVER, ADC AND CLOCK", 3.0, bold=True)
    s.text(20.32, 31.75, "Single-ended to differential at gain 1, 10 bit "
           "40 MSPS conversion, and the one 40 MHz oscillator that clocks "
           "the ADC, the controller and both synthesizers.", 1.5)
    y = 91.44
    a = k.port((30.48, y), "IF_AMP", "input", "l")
    e = k.h("C", s.wire(a, (a[0] + 4 * P, y)), "1uF")
    e = k.h("R", s.wire(e, (e[0] + 2 * P, y)), "402R")
    na = s.wire(e, (e[0] + 4 * P, y))
    drv = k.ic(parts.THS4541, "IN-", (na[0] + 3 * P, y))
    s.wire(na, drv.pin("IN-"))
    v = k.vdd(drv, "VS+", "+3V3_RF")
    pd = drv.pin("~{PD}")
    s.wire(pd, (pd[0], v[1]), v)
    k.vss(drv, "VS-")
    fb = drv.pin("FB+")
    yt = g(fb[1] - 4 * P)
    r = k.h("R", s.wire(na, (na[0], yt), (na[0] + 4 * P, yt)), "402R")
    s.wire(r, (fb[0], yt), fb)
    nb = drv.pin("IN+")
    nb = s.wire(nb, (nb[0] - 3 * P, nb[1]))
    g0 = (nb[0] - 9 * P, nb[1])
    k.gnd(s.wire(g0, (g0[0], g0[1] + P)))
    e = k.h("C", g0, "1uF", above=False)
    e = k.h("R", s.wire(e, (e[0] + P, e[1])), "402R", above=False)
    s.wire(e, nb)
    fb = drv.pin("FB-")
    yb = g(fb[1] + 4 * P)
    r = k.h("R", s.wire(nb, (nb[0], yb), (nb[0] + 4 * P, yb)), "402R",
            above=False)
    s.wire(r, (fb[0], yb), fb)
    k.net(drv, "VOCM", "VCM")
    s.text(drv.x, y - 30.0, "ADC driver\nFB+ and FB- are the outputs, "
           "brought out beside the inputs", 1.2, "bottom")
    op, on = drv.pin("OUT+"), drv.pin("OUT-")
    p = k.h("R", s.wire(op, (op[0] + 2 * P, op[1])), "33R")
    n = k.h("R", s.wire(on, (on[0] + 2 * P, on[1])), "33R", above=False)
    p = s.wire(p, (p[0] + 3 * P, p[1]))
    n = s.wire(n, (n[0] + 3 * P, n[1]))
    s.wire(k.v("C", p, "22pF"), n)
    u = k.ic(parts.ADC, "VIN+", (p[0] + 12 * P, p[1]))
    s.wire(p, u.pin("VIN+"))
    s.wire(n, u.pin("VIN-"))
    k.vdd(u, "AVDD", "+1V8_A")
    k.vdd(u, "DRVDD", "+3V3", rise=4 * P)
    k.vss(u, "AGND")
    k.shunt("C", k.name(u.pin("VCM"), "VCM", "l", stub=13 * P), "100nF",
            left=True)
    q = u.pin("VREF")
    s.wire(q, (q[0] - 9 * P, q[1]))
    k.shunt("C", (q[0] - 9 * P, q[1]), "1uF", left=True)
    k.shunt("C", (q[0] - 5 * P, q[1]), "100nF", left=True)
    q = u.pin("SENSE")
    k.gnd(s.wire(q, (q[0] - 2 * P, q[1]), (q[0] - 2 * P, q[1] + P)))
    q = u.pin("RBIAS")
    k.shunt("R", s.wire(q, (q[0] - 5 * P, q[1])), "10k", left=True)
    q = u.pin("CLK+")
    c0 = (q[0] - 14 * P, q[1])
    k.name(c0, "ADC_CLK", "l")
    e = k.h("R", c0, "49R9")
    m = s.wire(e, (e[0] + 2 * P, e[1]))
    k.shunt("R", m, "49R9", left=True)
    e = k.h("C", s.wire(m, (m[0] + 3 * P, m[1])), "100nF")
    s.wire(e, q)
    q = u.pin("CLK-")
    k.shunt("C", s.wire(q, (q[0] - 2 * P, q[1])), "100nF", left=True)
    s.text(c0[0] - 12.0, c0[1] + 9.0, "3.3 V CMOS halved\nand AC "
           "coupled", 1.2, "top")
    k.net(u, "CSB", "ADC.~{CS}")
    k.net(u, "SCLK/DFS", "ADC.SCK")
    k.net(u, "SDIO/PDWN", "ADC.SDIO")
    ends = [k.net(u, "D%d" % i, "D%d" % i, stub=5.08) for i in range(9, -1,
                                                                    -1)]
    xb = ends[0][0] + P
    for e in ends:
        s.bus_entry(e, P, -P)
    top = (xb, ends[0][1] - 3 * P)
    s.wire((xb, ends[-1][1] - P), top, (xb + 12 * P, top[1]), bus=True)
    s.hlabel((xb + 12 * P, top[1]), "D[0..9]", "output", "r")
    xr = xb + 12 * P
    for pin, name in (("DCO", "ADC_DCO"), ("MODE/OR", "ADC_OR")):
        q = u.pin(pin)
        k.port(q, name, "output", "r", run=xr - q[0])
    s.text(u.x + 20.0, u.y - 43.0, "D9 is the MSB.  Pin numbers with a "
           "\"?\" are not\nchecked against the SD9609 data sheet.", 1.2,
           "left bottom")
    s.text(u.x + 20.0, u.y + 10.0, "SENSE to ground: internal 1 V "
           "reference,\n2 V p-p full scale", 1.2, "left top")

    yc = 228.6
    s.frame(25.4, yc - 14 * P, 190.5, yc + 16 * P, "Clock: 40 MHz to the "
            "ADC, the controller, LO1 and LO2")
    osc = s.place(parts.OSC, 48.26, yc, value="40MHz", fields={
        "PartNumber": "ECS-2520MV-400-BN-TR", "Manufacturer": "ECS"},
        ref_at=(2.0, -9.5), val_at=(2.0, -7.4))
    k.vdd(osc, "VDD", "+3V3_RF")
    k.vss(osc, "GND")
    t = osc.pin("Tri-State")
    k.rail(s.wire(t, (t[0] - P, t[1]), (t[0] - P, t[1] - 4 * P)), "+3V3_RF")
    o = osc.pin("OUT")
    e = k.h("R", s.wire(o, (o[0] + 2 * P, o[1])), "33R")
    buf = k.ic(parts.LMK1C1104, "CLKIN", (e[0] + 5 * P, e[1]))
    s.wire(e, buf.pin("CLKIN"))
    v = k.vdd(buf, "VDD", "+3V3_RF")
    g1 = buf.pin("1G")
    s.wire(g1, (g1[0], v[1]), v)
    k.vss(buf, "GND")
    for pin, name in (("Y0", "ADC_CLK"), ("Y1", None), ("Y2", "REF1.P"),
                      ("Y3", "REF2.P")):
        q = buf.pin(pin)
        e = k.h("R", s.wire(q, (q[0] + 2 * P, q[1])), "33R")
        if name:
            k.name(e, name, "r")
        else:
            k.port(e, "CLK_MCU", "output", "r", run=6 * P)
    for i, name in enumerate(("REF1.N", "REF2.N")):
        a = (152.4, yc - 5 * P + i * 6 * P)
        k.name(a, name, "l")
        e = k.h("R", a, "0R")
        k.gnd(s.wire(e, (e[0] + P, e[1]), (e[0] + P, e[1] + P)))
    s.text(139.7, yc + 6 * P, "the synthesizers' other\nreference pins: AC "
           "ground", 1.2, "top")
    k.breakout((213.36, yc - 6 * P), "REF1{P N}", ["P", "N"], "output", "r")
    k.breakout((213.36, yc + 2 * P), "REF2{P N}", ["P", "N"], "output", "r")
    k.breakout((30.48, 160.02), "ADC{ADC_CTRL}", ["~{CS}", "SCK", "SDIO"],
               "bidirectional")
    k.decoupling(266.7, 165.1, [
        ("+1V8_A", [("100nF", "U701"), ("100nF", "U701"), ("100nF", "U701"),
                    ("100nF", "U701"), ("10uF", "")]),
        ("+3V3", [("100nF", "U701"), ("10uF", "")]),
        ("+3V3_RF", [("100nF", "U700"), ("10nF", "U700"), ("100nF", "Y700"),
                     ("100nF", "U702")])])
    return s


GPIO = {0: "D0", 1: "D1", 2: "D2", 3: "D3", 4: "D4", 5: "D5", 6: "D6",
        7: "D7", 8: "D8", 9: "D9", 10: "ADC_DCO", 11: "ADC_OR",
        12: "LO1.MUX", 13: "LO2.MUX", 14: "SPI_SCK", 15: "SPI_SDI",
        16: "LO1.~{CS}", 17: "LO1.CE", 18: "LO2.~{CS}", 19: "LO2.CE",
        20: "LO1.RC", 21: "LO1.RD", 22: "LO2.RC", 23: "LO2.RD",
        24: "RFIN.LE", 25: "RFIN.V1", 26: "RFIN.V2", 27: "FEL.SEL_1",
        28: "FEL.PRE_BYP", 29: "FEH.SEL_1", 30: "FEH.PRE_BYP",
        31: "SEL_HIGH", 32: "IF.LE", 33: "IF.SEL_MIX", 34: "ADC.~{CS}",
        35: "ADC.SCK", 36: "ADC.SDIO", 37: "LED"}


def controller(d):
    s = Sheet(d, "controller.kicad_sch", "Controller: RP2350B, flash, USB",
              paper="A3", base=800, paths=[UU["controller"]])
    k = Kit(s)
    s.text(20.32, 25.4, "CONTROLLER", 3.0, bold=True)
    s.text(20.32, 31.75, "Captures the ADC with PIO on GPIO0 to 11, sets "
           "the synthesizers, attenuators and switches, and talks to the "
           "PC over USB.", 1.5)
    u = s.place(parts.RP2350B, 215.9, 147.32, ref_at=(-22.0, 60.5),
                val_at=(-22.0, 62.6))
    for n in range(48):
        pin = "GPIO%d" % n if n < 40 else "GPIO%d/ADC%d" % (n, n - 40)
        if n in GPIO:
            k.net(u, pin, GPIO[n])
        else:
            s.nc(u.pin(pin))
    for pin, name in (("~{QSPI_SS}", "QSPI_SS"), ("QSPI_SCLK", "QSPI_SCLK"),
                      ("QSPI_SD0", "QSPI_SD0"), ("QSPI_SD1", "QSPI_SD1"),
                      ("QSPI_SD2", "QSPI_SD2"), ("QSPI_SD3", "QSPI_SD3"),
                      ("USB_DM", "USB_D-"), ("USB_DP", "USB_D+"),
                      ("RUN", "RUN"), ("XIN", "CLK_MCU"),
                      ("SWCLK", "SWCLK"), ("SWDIO", "SWDIO")):
        k.net(u, pin, name)
    s.nc(u.pin("XOUT"))
    k.vss(u, "GND", "VREG_PGND")
    # supplies along the top
    bar = g(u.pin("IOVDD")[1] - 2 * P)
    pins = [u.pin(n) for n in ("USB_OTP_VDD", "ADC_AVDD", "QSPI_IOVDD",
                               "IOVDD", "VREG_VIN")]
    for q in pins:
        s.wire(q, (q[0], bar))
    s.wire((pins[0][0], bar), (pins[-1][0], bar))
    k.pull_wire((pins[0][0], bar), "+3V3")
    q = u.pin("VREG_AVDD")
    k.name(s.wire(q, (q[0], bar - 3 * P)), "VREG_AVDD", "l")
    dv, fbk, lx = u.pin("DVDD"), u.pin("VREG_FB"), u.pin("VREG_LX")
    s.wire(fbk, (fbk[0], bar), (dv[0], bar))
    s.wire(dv, (dv[0], bar))
    k.rail(s.wire((dv[0], bar), (dv[0] + 4 * P, bar),
                  (dv[0] + 4 * P, bar - P)), "+1V1")
    k.name(s.wire(lx, (lx[0], bar - 3 * P)), "VREG_LX", "r")

    # the core regulator's parts
    x0, y0 = 264.16, 66.04
    s.frame(x0 - 5 * P, y0 - 9 * P, x0 + 50 * P - 55.88, y0 + 8 * P,
            "Core supply, 1.1 V")
    a = k.name((x0 + 6 * 1.27, y0), "VREG_LX", "l")
    e = k.h("L", (x0 + 6 * 1.27, y0), "3.3uH", fields={
        "PartNumber": "LQM21PN3R3MGRD", "Manufacturer": "Murata",
        "Footprint": "Inductor_SMD:L_0805_2012Metric"})
    m = s.wire(e, (e[0] + 3 * P, y0))
    k.shunt("C", m, "4.7uF")
    m2 = s.wire(m, (m[0] + 5 * P, y0))
    k.shunt("C", m2, "4.7uF")
    m3 = s.wire(m2, (m2[0] + 5 * P, y0))
    k.pull_wire(m3, "+1V1")
    k.flag((m2[0] + 2 * P, y0))
    x1 = m3[0] + 8 * P
    k.pull_wire((x1, y0), "+3V3")
    e = k.h("R", (x1, y0), "33R")
    m = s.wire(e, (e[0] + 3 * P, y0))
    k.shunt("C", m, "4.7uF")
    k.flag((m[0] + 3 * P, y0))
    k.name(m, "VREG_AVDD", "r", stub=8 * P)

    # flash
    f = s.place(parts.FLASH, 86.36, 81.28, ref_at=(2.0, -15.5),
                val_at=(2.0, -13.4))
    k.vdd(f, "VCC", "+3V3")
    k.vss(f, "GND")
    for pin, name in (("~{CS}", "QSPI_SS"), ("CLK", "QSPI_SCLK"),
                      ("DI/IO_{0}", "QSPI_SD0"), ("DO/IO_{1}", "QSPI_SD1"),
                      ("~{WP}/IO_{2}", "QSPI_SD2"),
                      ("~{HOLD}/~{RESET}/IO_{3}", "QSPI_SD3")):
        k.net(f, pin, name)
    e = (45.72, 55.88)
    k.name(e, "QSPI_SS", "l")
    k.pull("R", e, "10k", "+3V3")
    e = k.h("R", s.wire(e, (e[0] + 5 * P, e[1])), "1k")
    b = k.ic(parts.BUTTON, "1", (e[0] + 3 * P, e[1]), value="BOOTSEL",
             fields={"Footprint": "Button_Switch_SMD:SW_SPST_B3U-1000P",
                     "PartNumber": "B3U-1000P", "Manufacturer": "Omron"})
    s.wire(e, b.pin("1"))
    q = b.pin("2")
    k.gnd(s.wire(q, (q[0] + P, q[1]), (q[0] + P, q[1] + P)))

    # reset
    e = (45.72, 111.76)
    k.name(e, "RUN", "l")
    k.pull("R", e, "10k", "+3V3")
    m = s.wire(e, (e[0] + 4 * P, e[1]))
    k.shunt("C", m, "100nF")
    b = k.ic(parts.BUTTON, "1", (m[0] + 4 * P, m[1]), value="RESET",
             fields={"Footprint": "Button_Switch_SMD:SW_SPST_B3U-1000P",
                     "PartNumber": "B3U-1000P", "Manufacturer": "Omron"})
    s.wire(m, b.pin("1"))
    q = b.pin("2")
    k.gnd(s.wire(q, (q[0] + P, q[1]), (q[0] + P, q[1] + P)))

    # USB
    j = s.place(parts.USB_C, 40.64, 172.72, ref_at=(-10.0, -27.5),
                val_at=(-10.0, -25.4), value="USB-C", fields={
                    "Footprint": "Connector_USB:USB_C_Receptacle_GCT_"
                    "USB4105-xx-A_16P_TopMnt_Horizontal",
                    "PartNumber": "USB4105-GF-A", "Manufacturer": "GCT"})
    k.vss(j, "GND", "SHIELD")
    q = j.pin("VBUS")
    m = s.wire(q, (q[0] + 14 * P, q[1]))
    k.pull_wire(m, "VBUS")
    k.flag((m[0] - 3 * P, m[1]))
    k.shunt("R", s.wire(j.pin("CC1"), (j.pin("CC1")[0] + 9 * P,
                                        j.pin("CC1")[1])), "5k1")
    k.shunt("R", s.wire(j.pin("CC2"), (j.pin("CC2")[0] + 4 * P,
                                        j.pin("CC2")[1])), "5k1")
    for a_, b_, name in (("A7", "B7", "USBC_D-"), ("A6", "B6", "USBC_D+")):
        pa, pb = j.pin(a_), j.pin(b_)
        s.wire(pb, (pb[0] + P, pb[1]), (pa[0] + P, pa[1]))
        k.name(pa, name, "r")
    s.nc(j.pin("SBU1"))
    s.nc(j.pin("SBU2"))
    esd = s.place(parts.USB_ESD, 116.84, 177.8, ref_at=(2.0, -9.6),
                  val_at=(2.0, -7.5))
    k.vss(esd, "GND")
    k.vdd(esd, "VBUS", "VBUS")
    k.net(esd, "1", "USBC_D+")
    k.net(esd, "3", "USBC_D-")
    e = k.h("R", s.wire(esd.pin("6"), (esd.pin("6")[0] + 2 * P,
                                       esd.pin("6")[1])), "27R")
    k.name(e, "USB_D+", "r")
    q = esd.pin("4")
    e = k.h("R", s.wire(q, (q[0] + 2 * P, q[1]), (q[0] + 2 * P,
                                                   q[1] + 3 * P),
                        (q[0] + 3 * P, q[1] + 3 * P)), "27R", above=False)
    k.name(e, "USB_D-", "r")
    s.text(27.94, 212.0, "5k1 on CC1 and CC2: asks a Type-C source for 5 V."
           "  The board draws about 750 mA,\nso it needs a port that offers "
           "1.5 A (the firmware cannot check this).", 1.2, "left top")

    # debug, LED
    h = s.place(parts.HEADER3, 53.34, 246.38, value="SWD", fields={
        "Footprint": "Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_"
        "Vertical"}, ref_at=(0, -7.0), val_at=(0, 7.0), justify=None)
    k.net(h, "1", "SWCLK")
    q = h.pin("2")
    k.gnd(s.wire(q, (q[0] - 2 * P, q[1]), (q[0] - 2 * P, q[1] + 4 * P)))
    k.net(h, "3", "SWDIO")
    a = (83.82, 246.38)
    k.name(a, "LED", "l")
    e = k.h("R", a, "1k")
    led = k.ic(parts.LED, "A", (e[0] + 2 * P, e[1]), mirror=True,
               value="green", ref_at=(0, -5.5), val_at=(0, -3.4),
               justify=None, fields={"Footprint": "LED_SMD:LED_0603_"
                                     "1608Metric"})
    s.wire(e, led.pin("A"))
    q = led.pin("K")
    k.gnd(s.wire(q, (q[0] + P, q[1]), (q[0] + P, q[1] + P)))

    # the one SPI port, fanned out through 33 ohm to each device
    x0, y0 = 304.8, 104.14
    s.frame(x0 - 13 * P, y0 - 5 * P, x0 + 14 * P, y0 + 25 * P,
            "SPI fan-out")
    row = 0
    for src in ("SPI_SCK", "SPI_SDI"):
        for dst in ("RFIN", "IF", "LO1", "LO2"):
            a = (x0, y0 + row * 3 * P)
            k.name(a, src, "l")
            e = k.h("R", a, "33R")
            k.name(e, "%s.%s" % (dst, src[4:]), "r")
            row += 1

    # the sheet's edge
    xr, yy = 381.0, 55.88
    for bus, members, shape in (
            ("D[0..9]", ["D%d" % i for i in range(10)], "input"),
            ("ADC{ADC_CTRL}", ALIASES["ADC_CTRL"], "bidirectional"),
            ("IF{IF_CTRL}", ALIASES["IF_CTRL"], "output"),
            ("FEH{FE_CTRL}", ALIASES["FE_CTRL"], "output"),
            ("FEL{FE_CTRL}", ALIASES["FE_CTRL"], "output"),
            ("RFIN{IN_CTRL}", ALIASES["IN_CTRL"], "output"),
            ("LO1{SYN_CTRL}", ALIASES["SYN_CTRL"], "bidirectional"),
            ("LO2{SYN_CTRL}", ALIASES["SYN_CTRL"], "bidirectional")):
        k.breakout((xr, yy), bus, members, shape, "r")
        yy += (len(members) + 3) * P
    for name, shape in (("ADC_DCO", "input"), ("ADC_OR", "input"),
                        ("CLK_MCU", "input"), ("SEL_HIGH", "output")):
        k.name(k.port((xr, yy), name, shape, "r"), name, "l")
        yy += 2 * P
    k.decoupling(134.62, 233.68, [
        ("+3V3", [("100nF", "IOVDD")] * 8 + [("100nF", "QSPI"),
                                              ("100nF", "USB/OTP"),
                                              ("100nF", "ADC"),
                                              ("100nF", "U801"),
                                              ("10uF", "")]),
        ("+1V1", [("100nF", "DVDD"), ("100nF", "DVDD"),
                  ("100nF", "DVDD")])])
    return s


def power(d):
    s = Sheet(d, "power.kicad_sch", "Power: USB 5 V to the supply rails",
              paper="A3", base=900)
    k = Kit(s)
    s.text(20.32, 25.4, "POWER", 3.0, bold=True)
    s.text(20.32, 31.75, "USB 5 V, filtered, feeds the 5 V amplifiers "
           "directly and a low-noise regulator for each 3.3 V and 1.8 V "
           "rail.", 1.5)
    y = 71.12
    a = (38.1, y)
    k.pull_wire(a, "VBUS")
    bead = {"PartNumber": "BLM15PX601SN1D", "Manufacturer": "Murata"}
    for net, caps in (("VBUS_F", ["10uF", "100nF"]),
                      ("+5V_RF", ["10uF", "100nF"]),
                      ("+5V_A", ["10uF", "100nF"])):
        e = k.h("FB", s.wire(a, (a[0] + 3 * P, y)), "600R@100MHz",
                fields=bead)
        m = s.wire(e, (e[0] + 4 * P, y))
        for c in caps:
            k.shunt("C", m, c)
            m = s.wire(m, (m[0] + 4 * P, y))
        k.flag((m[0] - 2 * P, y))
        k.pull_wire(m, net)
        a = m
    s.text(38.1, y + 14.0, "VBUS_F: regulator inputs.  +5V_RF: the four "
           "PMA3-83LN+.  +5V_A: the two IF amplifiers.", 1.2, "left top")
    cells = (("+3V3", parts.LDO, "controller, flash, ADC outputs: 120 mA"),
             ("+3V3_RF", parts.LDO, "switches, attenuators, low band "
              "preamp, clock, ADC driver: 150 mA"),
             ("+1V8_A", parts.LDO18, "ADC core: 50 mA"),
             ("G_3V3_SYN", parts.LDO, "both synthesizers: 110 mA"),
             ("G_3V3_BUF", parts.LDO, "both synthesizers' outputs: 60 mA"))
    for i, (net, sym, what) in enumerate(cells):
        x = 66.04 + (i % 3) * 114.3
        yy = 137.16 + (i // 3) * 63.5
        u = k.ldo(x, yy, sym, net, flag=False)
        s.text(x - 20.0, yy + 19.0, what, 1.2, "left top")
    k.gnd(s.wire((320.04, 208.28), (320.04, 210.82)))
    k.flag((320.04, 208.28))
    s.text(292.1, 222.0, "Total about 750 mA at 5 V: more than a USB 2.0 "
           "port's 500 mA.\nUse a Type-C port that offers 1.5 A or more.",
           1.2, "left top")
    return s


class _Existing:
    """A sheet file that is the project's own, not written here."""

    def __init__(self, filename, title, paths, hier):
        self.filename, self.title, self.paths, self.hier = (filename, title,
                                                            paths, hier)


LO_SHEET = _Existing("lo.kicad_sch", "LO", [UU["lo1"], UU["lo2"]],
                     [("LO_A{P N}", "output"), ("LO_B{P N}", "output"),
                      ("REF{P N}", "input"),
                      ("SYN{SYN_CTRL}", "bidirectional")])


def root(d, sh):
    s = Sheet(d, "spectre.kicad_sch", "Spectre: 0.1 MHz to 6.4 GHz "
              "spectrum analyzer", paper="A3", paths=[""])
    k = Kit(s)
    page = [1]

    def box(child, x, y, w, h, pins, name=None, instance=0):
        shapes = dict(child.hier)
        page[0] += 1
        return s.sheet_symbol(child, x, y, w, h,
                              [(n, shapes[n], side, off)
                               for n, side, off in pins], page[0],
                              name=name, instance=instance)

    def stub(pt, name, side, bus=True, drop=2 * P):
        """A short bus (or wire) from a sheet pin, carrying its name: the
        other end of the net is the stub of the same name."""
        plain = name.replace("~{", "").replace("}", "").replace("{", " ")
        n = (int((len(plain) * 1.1 + 2.0) / 1.27) + 1) * 1.27
        x, y = pt
        if side == "l":
            a, b = (g(x - n), y), (x, y)
        elif side == "r":
            a, b = (x, y), (g(x + n), y)
        else:
            y2 = g(y + (drop if side == "b" else -drop))
            s.wire((x, y), (x, y2), bus=bus)
            a, b = (x, y2), (g(x + n), y2)
        s.wire(a, b, bus=bus)
        # the name at the free end, reading back along the stub
        if side == "l":
            s.label(a, name)
        else:
            s.label(b, name, side="l")

    y0 = 71.12                     # the top of the main row
    # --- the LO rows, above the row they feed
    lo_out = {}
    for i, (yy, n) in enumerate(((43.18, 1), (20.32, 2))):
        e = box(LO_SHEET, 55.88, yy, 38.1, 17.78,
                [("REF{P N}", "l", 5.08), ("SYN{SYN_CTRL}", "l", 12.7),
                 ("LO_A{P N}", "r", 8.89), ("LO_B{P N}", "r", 15.24)],
                name="LO%d" % n, instance=n - 1)
        stub(e["REF{P N}"], "REF%d{P N}" % n, "l")
        stub(e["SYN{SYN_CTRL}"], "LO%d{SYN_CTRL}" % n, "l")
        f = box(sh["lo_drive"], 119.38, yy, 30.48, 17.78,
                [("LO{P N}", "l", 8.89), ("LO_OUT", "r", 8.89)],
                name="LO%d Drive" % n, instance=n - 1)
        s.wire(e["LO_A{P N}"], f["LO{P N}"], bus=True)
        s.label((e["LO_A{P N}"][0] + 2.54, e["LO_A{P N}"][1]),
                "LO%d_RF{P N}" % n)
        lo_out[n] = f["LO_OUT"]

    # --- the signal path, left to right
    rf = box(sh["rf_input"], 25.4, y0, 35.56, 88.9,
             [("RF_L1", "r", 7.62), ("RF_L2", "r", 15.24),
              ("RF_HIGH", "r", 53.34), ("IF_DIRECT", "r", 81.28),
              ("RFIN{IN_CTRL}", "b", 10.16)], name="RF Input")
    fl = box(sh["fe_low"], 86.36, y0, 40.64, 22.86,
             [("RF_L1", "l", 7.62), ("RF_L2", "l", 15.24),
              ("RF_LOW", "r", 10.16), ("FEL{FE_CTRL}", "b", 10.16)],
             name="Low Band Front End")
    fh = box(sh["fe_high"], 86.36, y0 + 43.18, 40.64, 22.86,
             [("RF_HIGH", "l", 10.16), ("RF_HIGH_OUT", "r", 10.16),
              ("FEH{FE_CTRL}", "t", 10.16)], name="High Band Front End")
    i1 = box(sh["if_1"], 157.48, y0, 45.72, 66.04,
             [("RF_LOW", "l", 10.16), ("RF_HIGH", "l", 53.34),
              ("IF_MIX", "r", 10.16), ("LO1", "t", 12.7),
              ("LO2", "t", 27.94), ("SEL_HIGH", "b", 22.86)],
             name="First IF Stage")
    i2 = box(sh["if_2"], 231.14, y0, 40.64, 88.9,
             [("IF_MIX", "l", 10.16), ("IF_DIRECT", "l", 81.28),
              ("IF_AMP", "r", 10.16), ("IF{IF_CTRL}", "b", 20.32)],
             name="Second IF Stage")
    ad = box(sh["adc"], 297.18, y0, 40.64, 88.9,
             [("IF_AMP", "l", 10.16), ("D[0..9]", "r", 10.16),
              ("ADC_DCO", "r", 20.32), ("ADC_OR", "r", 27.94),
              ("CLK_MCU", "r", 38.1), ("ADC{ADC_CTRL}", "r", 48.26),
              ("REF1{P N}", "b", 10.16), ("REF2{P N}", "b", 27.94)],
             name="Driver, ADC & Clock")
    names = ["IF{IF_CTRL}", "SEL_HIGH", "FEH{FE_CTRL}", "FEL{FE_CTRL}",
             "RFIN{IN_CTRL}", "LO1{SYN_CTRL}", "LO2{SYN_CTRL}"]
    co = box(sh["controller"], 363.22, y0, 35.56, 139.7,
             [("D[0..9]", "l", 10.16), ("ADC_DCO", "l", 20.32),
              ("ADC_OR", "l", 27.94), ("CLK_MCU", "l", 38.1),
              ("ADC{ADC_CTRL}", "l", 48.26)]
             + [(n, "l", 71.12 + 10.16 * i) for i, n in enumerate(names)],
             name="Controller")
    box(sh["power"], 86.36, 177.8, 35.56, 20.32, [], name="Power")

    for a, b in ((rf["RF_L1"], fl["RF_L1"]), (rf["RF_L2"], fl["RF_L2"]),
                 (rf["RF_HIGH"], fh["RF_HIGH"]), (fl["RF_LOW"], i1["RF_LOW"]),
                 (fh["RF_HIGH_OUT"], i1["RF_HIGH"]),
                 (i1["IF_MIX"], i2["IF_MIX"]),
                 (rf["IF_DIRECT"], i2["IF_DIRECT"]),
                 (i2["IF_AMP"], ad["IF_AMP"]),
                 (ad["ADC_DCO"], co["ADC_DCO"]), (ad["ADC_OR"], co["ADC_OR"]),
                 (ad["CLK_MCU"], co["CLK_MCU"])):
        s.wire(a, b)
    s.wire(ad["D[0..9]"], co["D[0..9]"], bus=True)
    s.wire(ad["ADC{ADC_CTRL}"], co["ADC{ADC_CTRL}"], bus=True)
    for n in (1, 2):
        t = i1["LO%d" % n]
        s.wire(lo_out[n], (t[0], lo_out[n][1]), t)
    # --- controls and clock references go by name
    stub(rf["RFIN{IN_CTRL}"], "RFIN{IN_CTRL}", "b")
    stub(fl["FEL{FE_CTRL}"], "FEL{FE_CTRL}", "b")
    stub(fh["FEH{FE_CTRL}"], "FEH{FE_CTRL}", "t")
    stub(i1["SEL_HIGH"], "SEL_HIGH", "b", bus=False)
    stub(i2["IF{IF_CTRL}"], "IF{IF_CTRL}", "b")
    stub(ad["REF1{P N}"], "REF1{P N}", "b")
    stub(ad["REF2{P N}"], "REF2{P N}", "b", drop=5 * P)
    for n in names:
        stub(co[n], n, "l", bus="{" in n)

    # --- what the blocks are
    for x, y, t in (
            (25.4, y0 - 6.0, "0.1 MHz - 6.4 GHz\nattenuator, band select"),
            (86.36, y0 + 26.5, ""),
            (157.48, y0 + 71.0, "IF1 = 3.4 GHz\nLO1 = f + 3.4 GHz\n"
             "LO2 = 3.388 / 3.402 GHz (low band)\nLO2 = f +/- 12 MHz "
             "(high band)"),
            (231.14, y0 - 6.0, "IF2 = 12 MHz\n58 dB, anti-alias 17.5 MHz"),
            (297.18, y0 - 6.0, "10 bit, 40 MSPS\n40 MHz reference"),
            (363.22, y0 - 6.0, "RP2350B, USB")):
        if t:
            s.text(x, y, t, 1.27, "left bottom" if y < y0 else "left top")
    s.text(86.36, y0 - 2.6, "15 MHz - 3.0 GHz", 1.27, "left bottom")
    s.text(86.36, y0 + 71.0, "3.0 - 6.4 GHz", 1.27, "left top")
    s.text((rf["IF_DIRECT"][0] + i2["IF_DIRECT"][0]) / 2,
           rf["IF_DIRECT"][1] - 1.0, "direct path, 0.1 - 15 MHz", 1.27,
           "bottom")
    s.text(25.4, 215.9, "SPECTRE", 5.0, "left bottom", bold=True)
    s.text(25.4, 219.0, "Spectrum analyzer, 0.1 MHz to 6.4 GHz.  Low band "
           "to 3 GHz by a 3.4 GHz first IF; high band converted directly; "
           "0.1 to 15 MHz sampled directly.\nThe signal runs left to "
           "right along the middle row.  Controls and clock references "
           "are joined by name: a bus stub carries the same name at both "
           "ends.\nDesign, simulation and what it gives up: "
           "sim/README.md.  How this schematic is made and what is still "
           "open: docs/schematic.md.", 1.5, "left top")
    return s


def build():
    d = Design("spectre", ROOT)
    sheets = {"rf_input": rf_input(d), "fe_low": fe_low(d),
              "fe_high": fe_high(d), "if_1": if_1(d),
              "lo_drive": lo_drive(d), "if_2": if_2(d), "adc": adc(d),
              "controller": controller(d), "power": power(d)}
    sheets["root"] = root(d, sheets)
    return d, sheets
