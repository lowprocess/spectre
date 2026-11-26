#!/usr/bin/env python3
"""
Draw the analyzer's block diagram: block_diagram.svg, beside this file.

    python make_block_diagram.py            the standalone SVG (light and dark)
    python make_block_diagram.py --inline   the bare <svg> on stdout, styled by
                                            the page it is put in (the classes
                                            and colour variables of STYLE)

The drawing is the design that sasim.analyzer builds: change both together.
"""

import os
import sys

W, H = 1392, 840
YIN = 331

out = []


def add(s):
    out.append(s)


def text(x, y, s, cls, anchor="middle", extra=""):
    add('<text x="%g" y="%g" class="%s" text-anchor="%s"%s>%s</text>'
        % (x, y, cls, anchor, extra, s))


def block(x, y, w, lines, printed=False, h=52):
    """A box centred on the row y, its left edge at x; lines: the name, then
    up to two details."""
    add('<rect x="%g" y="%g" width="%g" height="%g" rx="4" class="blk%s"/>'
        % (x, y - h / 2, w, h, " printed" if printed else ""))
    n = len(lines)
    y0 = y - (n - 1) * 6.5 + 4
    for i, s in enumerate(lines):
        text(x + w / 2, y0 + i * 13, s, "t1" if i == 0 else "t2")
    return x + w


def pad(x, y, label="3 dB", w=34):
    add('<rect x="%g" y="%g" width="%g" height="34" rx="4" class="blk"/>'
        % (x, y - 17, w))
    text(x + w / 2, y + 4, label, "t2")
    return x + w


def switch(x, y0, y1, label, w=40):
    add('<rect x="%g" y="%g" width="%g" height="%g" rx="4" class="blk"/>'
        % (x, y0, w, y1 - y0))
    cx, cy = x + w / 2, (y0 + y1) / 2
    text(cx, cy + 4, label, "t1", extra=' transform="rotate(-90 %g %g)"'
         % (cx, cy))
    return x + w


def mixer(cx, cy, r=17):
    add('<circle cx="%g" cy="%g" r="%g" class="mix"/>' % (cx, cy, r))
    d = r * 0.6
    add('<path d="M%g %g L%g %g M%g %g L%g %g" class="mixx"/>'
        % (cx - d, cy - d, cx + d, cy + d, cx - d, cy + d, cx + d, cy - d))


def wire(points, cls="w", arrow=True):
    """A polyline through the points, with an arrowhead at its end."""
    (x0, y0), (x1, y1) = points[-2], points[-1]
    dx, dy = x1 - x0, y1 - y0
    n = (dx * dx + dy * dy) ** 0.5
    ux, uy = dx / n, dy / n
    end = (x1 - ux * 6, y1 - uy * 6) if arrow else (x1, y1)
    pts = points[:-1] + [end]
    add('<polyline points="%s" class="%s"/>'
        % (" ".join("%g,%g" % p for p in pts), cls))
    if arrow:
        px, py = -uy, ux
        add('<polygon points="%g,%g %g,%g %g,%g" class="h%s"/>'
            % (x1, y1, x1 - ux * 8 + px * 3.6, y1 - uy * 8 + py * 3.6,
               x1 - ux * 8 - px * 3.6, y1 - uy * 8 - py * 3.6, cls))


def draw():
    text(24, 30, "RF FRONT END", "sec", "start")
    YL1, YL2, YL, YH1, YH2, YH = 150, 230, 190, 350, 430, 390
    YM2 = 290

    # ---- the common input
    add('<circle cx="34" cy="%g" r="5" class="mix"/>' % YIN)
    text(34, YIN - 16, "RF in", "t1")
    text(18, YIN + 44, "0.1 MHz to", "t2", "start")
    text(18, YIN + 57, "6.4 GHz", "t2", "start")
    wire([(39, YIN), (64, YIN)])
    x = block(64, YIN, 80, ["DC block", "+ limiter"])
    wire([(x, YIN), (x + 18, YIN)])
    x = block(x + 18, YIN, 80, ["Attenuator", "PE43704", "0–31.75 dB"])
    wire([(x, YIN), (x + 20, YIN)])
    sw1x = x + 20
    sw1 = switch(sw1x, 122, 540, "SW1 · PE42540 SP4T · band select")

    # ---- the low band: two input filters, then one path
    xa = sw1 + 26
    for y, name, lines, printed in (
            (YL1, "L1 · 15 MHz–2.29 GHz",
             ["Low-pass", "2× LFCN-2250+", "2.3 GHz"], False),
            (YL2, "L2 · 2.29–3.0 GHz",
             ["Band-pass", "interdigital, N=7", "2.3–3.0 GHz"], True)):
        text(sw1 + 8, y - 34, name, "lbl", "start")
        wire([(sw1, y), (xa, y)], "wa")
        x = block(xa, y, 96, lines, printed=printed)
        wire([(x, y), (x + 24, y)], "wa")
    x = switch(x + 24, 126, 254, "SW2")
    wire([(x, YL), (x + 14, YL)], "wa")
    x = block(x + 14, YL, 80, ["Low-pass", "radial stub", "4.0 GHz"],
              printed=True)
    wire([(x, YL), (x + 14, YL)], "wa")
    x = block(x + 14, YL, 108, ["Preamp", "TRF37D73", "~+21 dB, or bypass"])
    wire([(x, YL), (x + 14, YL)], "wa")
    x = pad(x + 14, YL)
    mx1 = x + 14 + 17
    wire([(x, YL), (mx1 - 17, YL)], "wa")
    mixer(mx1, YL)
    text(mx1, YL + 36, "MIX1 · SIM-83+", "t1")
    text(mx1, YL + 49, "in: IF port, out: RF port", "t2")
    x = mx1 + 17
    wire([(x, YL), (x + 14, YL)], "wa")
    x = block(x + 14, YL, 80, ["IF1 amp", "PMA3-83LN+", "+21 dB"])
    wire([(x, YL), (x + 14, YL)], "wa")
    x = pad(x + 14, YL, "6 dB")
    wire([(x, YL), (x + 14, YL)], "wa")
    x = block(x + 14, YL, 80, ["Low-pass", "radial stub", "4.0 GHz"],
              printed=True)
    wire([(x, YL), (x + 14, YL)], "wa")
    text(x + 14, YL - 36, "first IF 3.4 GHz", "lbl", "start")
    x = block(x + 14, YL, 80, ["Band-pass", "hairpin, N=5", "3.4 GHz"],
              printed=True)
    sw5 = x + 22
    wire([(x, YL), (sw5, YL)], "wa")

    add('<rect x="%g" y="34" width="156" height="46" rx="4" class="blk"/>'
        % (mx1 - 78))
    text(mx1, 53, "LO1 · LMX2572", "t1")
    text(mx1, 67, "f + 3.4 GHz: 3.4–6.4 GHz", "t2")
    wire([(mx1, 80), (mx1, YL - 17)], "wl")

    # ---- the high band: two preselectors
    wire([(sw1, YH), (xa, YH)], "wb")
    x3 = switch(xa, 326, 454, "SW3")
    for y, name, bpf, lpf in (
            (YH1, "H1 · 3.0–4.4 GHz", "3.0–4.5 GHz", "5.0 GHz"),
            (YH2, "H2 · 4.4–6.4 GHz", "4.3–6.4 GHz", "7.0 GHz")):
        text(x3 + 24, y - 32, name, "lbl", "start")
        wire([(x3, y), (x3 + 24, y)], "wb")
        x = block(x3 + 24, y, 84, ["Band-pass", "stub, N=5", bpf],
                  printed=True)
        wire([(x, y), (x + 16, y)], "wb")
        x = block(x + 16, y, 84, ["Low-pass", "radial stub", lpf],
                  printed=True)
        wire([(x, y), (x + 24, y)], "wb")
    x = switch(x + 24, 326, 454, "SW4")
    wire([(x, YH), (x + 28, YH)], "wb")
    x = block(x + 28, YH, 104, ["Preamp", "PMA3-83LN+", "+21 dB, or bypass"])
    wire([(x, YH), (sw5, YH)], "wb")

    # ---- the second mixer
    x = switch(sw5, 166, 414, "SW5 · mixer 2 select")
    mx2 = x + 66
    wire([(x, YM2), (mx2 - 17, YM2)])
    mixer(mx2, YM2)
    text(mx2 + 24, YM2 - 3, "MIX2", "t1", "start")
    text(mx2 + 24, YM2 + 10, "SIM-83+", "t2", "start")
    add('<rect x="%g" y="150" width="136" height="60" rx="4" class="blk"/>'
        % (mx2 - 54))
    text(mx2 + 14, 169, "LO2 · LMX2572", "t1")
    text(mx2 + 14, 183, "low band: 3.388 GHz", "t2")
    text(mx2 + 14, 196, "high band: f ± 12 MHz", "t2")
    wire([(mx2, 210), (mx2, YM2 - 17)], "wl")

    # ---- the IF row, and the two ways into it
    yr, x0, y6 = 770, 40, 690
    cx = sw1x + 20
    text(58, 640, "IF AND DIGITISER", "sec", "start")
    wire([(mx2, YM2 + 17), (mx2, yr), (x0, yr), (x0, y6), (64, y6)])
    text(mx2 - 12, yr - 8, "second IF · 12 MHz centre, 7–17 MHz kept",
         "lbl", "end")
    x = block(64, y6, 102, ["Diplexer", "low-pass 30 MHz", "HP arm to 50 Ω"])
    wire([(x, y6), (cx - 20, y6)])
    # the direct-sample path, out of the bottom of SW1
    wire([(cx, 540), (cx, 562)], "wb")
    add('<rect x="%g" y="562" width="96" height="44" rx="4" class="blk"/>'
        % (cx - 48))
    text(cx, 581, "Low-pass", "t1")
    text(cx, 594, "30 MHz", "t2")
    text(cx + 58, 581, "Direct · 0.1–15 MHz", "lbl", "start")
    text(cx + 58, 594, "no mixer: the ADC samples it", "t2", "start")
    wire([(cx, 606), (cx, y6 - 26)], "wb")
    add('<rect x="%g" y="%g" width="40" height="52" rx="4" class="blk"/>'
        % (cx - 20, y6 - 26))
    text(cx, y6 + 4, "SW6", "t1")
    x, w, g = cx + 20, 92, 22
    for i, lines in enumerate((
            ["IF amp", "LMH6629", "+26 dB"],
            ["Attenuator", "PE43711", "0–31.75 dB"],
            ["Anti-alias LPF", "elliptic, N=9", "17.5 MHz"],
            ["IF amp", "LMH6629", "+26 dB"],
            ["ADC driver", "THS4541", "+6 dB, diff."],
            ["ADC", "SD9609-40", "10 bit, 40 MSPS"],
            ["RP2350", "PIO capture", "FFT, control"],
            ["PC", "sweep, stitching", "display"])):
        wire([(x, y6), (x + g, y6)])
        if i == 5:
            adc = x + g + w / 2
        if i == 6:
            mcu = x + g + w / 2
            text(x + g / 2, y6 + 44, "10-bit", "t2")
        if i == 7:
            text(x + g / 2, y6 + 44, "USB", "t2")
        x = block(x + g, y6, w, lines)

    # ---- the clock
    yc = 606
    add('<rect x="%g" y="%g" width="92" height="40" rx="4" class="blk"/>'
        % (adc - 46, yc - 20))
    text(adc, yc - 2, "Oscillator", "t1")
    text(adc, yc + 11, "40 MHz", "t2")
    wire([(adc, yc + 20), (adc, y6 - 26)], "wc")
    wire([(adc + 46, yc), (mcu, yc), (mcu, y6 - 26)], "wc")
    text(adc - 58, yc - 2, "also the reference of LO1 and LO2", "t2", "end")
    text(adc - 58, yc + 11, "(10 and 2 MHz phase detectors, integer-N)",
         "t2", "end")
    text(mcu + 14, yc - 2, "SPI: LOs, attenuators", "t2", "start")
    text(mcu + 14, yc + 11, "GPIO: switches, preamps", "t2", "start")

    # ---- what a dashed outline means
    add('<rect x="24" y="808" width="26" height="16" rx="3" '
        'class="blk printed"/>')
    text(58, 820, "printed on the board (0.508 mm RO4003C), from dfsynth "
         "and mom25d", "t2", "start")


# the colours and type of the drawing; a page that takes the --inline form
# defines the same variables and classes
STYLE = """
svg { --bg: #f6f7f9; --surface: #ffffff; --fg: #17202b; --muted: #566273;
      --line: #b9c2ce; --a: #1d6fd6; --b: #c2571a;
      font-family: system-ui, -apple-system, "Segoe UI", Helvetica, Arial,
                   sans-serif; }
@media (prefers-color-scheme: dark) {
  svg { --bg: #12161c; --surface: #1b222b; --fg: #e6ebf1; --muted: #9aa6b4;
        --line: #465263; --a: #5aa2f5; --b: #f0914d; } }
.ground { fill: var(--bg); }
""" + """
.blk { fill: var(--surface); stroke: var(--line); stroke-width: 1.2; }
.blk.printed { stroke: var(--fg); stroke-dasharray: 4 3; }
.mix { fill: var(--surface); stroke: var(--fg); stroke-width: 1.4; }
.mixx { stroke: var(--fg); stroke-width: 1.4; fill: none; }
.t1 { fill: var(--fg); font-size: 11.5px; font-weight: 600; }
.t2 { fill: var(--muted); font-size: 10.5px; }
.lbl { fill: var(--fg); font-size: 12px; font-weight: 600; }
.sec { fill: var(--muted); font-size: 10.5px; font-weight: 600;
       letter-spacing: 0.09em; }
.w, .wa, .wb, .wl, .wc { fill: none; stroke-width: 1.7;
                         stroke-linejoin: round; }
.w { stroke: var(--fg); } .hw { fill: var(--fg); }
.wa { stroke: var(--a); } .hwa { fill: var(--a); }
.wb { stroke: var(--b); } .hwb { fill: var(--b); }
.wl { stroke: var(--muted); stroke-width: 1.3; } .hwl { fill: var(--muted); }
.wc { stroke: var(--muted); stroke-width: 1.3; stroke-dasharray: 5 4; }
.hwc { fill: var(--muted); }
"""
LABEL = ("Block diagram: RF in, a step attenuator and a four-way band "
         "switch. The low band, in two filtered halves to 3 GHz, is "
         "up-converted in the first mixer to a 3.4 GHz first IF and comes "
         "down to 12 MHz in the second. The high band, in two preselected "
         "halves to 6.4 GHz, goes straight into the second mixer. A direct "
         "path under 15 MHz goes to the IF chain with no mixer. The 12 MHz "
         "IF is amplified, filtered and sampled at 40 MSPS by a 10 bit ADC, "
         "and an RP2350 sends the captures to a PC.")


def svg(inline):
    del out[:]
    draw()
    head = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" '
            'role="img" aria-label="%s">' % (W, H, LABEL))
    if inline:
        return head + "\n" + "\n".join(out) + "\n</svg>\n"
    return (head + "\n<style>%s</style>\n" % STYLE
            + '<rect width="%d" height="%d" class="ground"/>\n' % (W, H)
            + "\n".join(out) + "\n</svg>\n")


if __name__ == "__main__":
    if "--inline" in sys.argv:
        sys.stdout.write(svg(True))
    else:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "block_diagram.svg")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(svg(False))
        print("wrote", path)
