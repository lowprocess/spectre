#!/usr/bin/env python3
"""
Run the spectrum analyzer's simulation: its budget, and the test cases that
show what it does with real signals.

    python run.py                  the board's chain: every case, figures and
                                   report.md in out/
    python run.py --design proposal
                                   the proposal's, to 6.4 GHz
    python run.py compare budget   chosen cases
    python run.py --list

The cases:
    compare       the board's chain against the proposal's, on the same tests
    budget        stage-by-stage gain, noise figure and IP3
    cw            a carrier at 1 GHz: its image, its skirts, the noise floor
    im3           two tones 1 MHz apart: third-order products against the
                  input attenuator
    direct        the direct-sample path, and what folds into it
    compression   reading against input level, to the ADC's clipping
    feedthrough   a signal on the first IF, seen from the superheterodyne path
    residuals     nothing connected: the analyzer's own spurs
    high          proposal: the high band: a carrier and its image, and a
                  bursting 18 MHz wide signal, which two captures show only
                  in pieces
    full          the whole span with several signals
    strong        one 0 dBm signal: every product the analyzer makes of it

Options: --design board|proposal, --att DB (input attenuator), --if-att DB,
--preamp (board: its input buffer; proposal: its preamps), --seed N,
--out DIR, --no-lna (board: without its 20 dB amplifier), --pads DB DB
(proposal: at the first mixer's IF port and after the IF1 amplifier).
"""

import argparse
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sasim import Analyzer, Signal, lo, parts  # noqa: E402

GHZ, MHZ = 1e9, 1e6
# the series colours: a validated categorical order (blue, orange, aqua)
C1, C2, C3 = "#257de0", "#f47230", "#00b894"
INK, INK2, GRID, AXIS = "#191919", "#666666", "#e7e7e7", "#c2c2c2"


def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "figure.dpi": 130, "savefig.dpi": 130, "font.size": 9,
        "axes.edgecolor": AXIS, "axes.labelcolor": INK2,
        "axes.titlecolor": INK, "axes.titlesize": 10,
        "axes.titleweight": "bold", "axes.titlelocation": "left",
        "xtick.color": INK2, "ytick.color": INK2, "text.color": INK,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
        "axes.spines.top": False, "axes.spines.right": False,
        "legend.frameon": False, "lines.linewidth": 1.0})
    return plt


def peak_trace(f, p, points=2400):
    """The trace as a display draws it: the peak of each bucket."""
    if f.size <= points:
        return f, p
    n = f.size // points
    m = (f.size // n) * n
    return (f[:m].reshape(-1, n).mean(1), p[:m].reshape(-1, n).max(1))


def reading(f, p, at, span=40e3):
    near = np.abs(f - at) <= span
    return float(p[near].max()) if near.any() else float("nan")


def level(f, p, at, span=40e3):
    """The mean power around `at`: what a noise marker reads."""
    near = np.abs(f - at) <= span
    return float(10 * np.log10(np.mean(10 ** (p[near] / 10))))


def floor_dbm(p):
    """The noise floor of a trace: its median, as power."""
    return float(np.median(p))


NO_FLOOR = "none: the ADC is not dithered"


def dither(sa, f=1.0e9):
    """The chain's noise at the ADC in LSB rms, and the input level of a
    tone one LSB in amplitude there.  Under about half an LSB of noise the
    converter rests on one code: it has no noise floor to read, and a signal
    under an LSB does not move it."""
    _, s = sa.budget(min(f, sa.top))
    return s["noise_at_adc_lsb"], float(s["one_lsb_dbm"])


def floor_text(sa, p):
    return ("%.1f" % floor_dbm(p) if dither(sa)[0] >= 0.5 else NO_FLOOR)


def why(sa, signals, f, reads, shifted=False):
    """The likeliest maker of the reading `reads` at f, as text."""
    found = sa.explain(signals, f, shifted, span=30e3)
    rf = [x for x in found if x[1] is not None]
    ifh = [x for x in found if x[1] is None]
    if rf and rf[0][1] > reads - 8.0:
        return "`%s`" % rf[0][2]
    if ifh:
        return ifh[0][2]
    if rf:
        return "`%s` (%.0f dBm of it)" % (rf[0][2], rf[0][1])
    wide = [x for x in sa.explain(signals, f, shifted, span=400e3)
            if x[1] is not None]
    return "the skirt of `%s`" % wide[0][2] if wide else "-"


def _under(cell, limit=-180.0):
    try:
        return float(cell) < limit
    except (TypeError, ValueError):
        return False


class Report:
    def __init__(self, out):
        self.out, self.lines = out, []
        os.makedirs(out, exist_ok=True)

    def say(self, text=""):
        print(text)
        self.lines.append(text)

    def table(self, head, rows):
        self.say("| " + " | ".join(head) + " |")
        self.say("|" + "|".join("---" for _ in head) + "|")
        for r in rows:
            r = ["no reading" if _under(c) else c for c in r]
            self.say("| " + " | ".join(str(c) for c in r) + " |")
        self.say()

    def figure(self, fig, name, caption):
        path = os.path.join(self.out, name)
        fig.savefig(path, bbox_inches="tight")
        import matplotlib.pyplot as plt
        plt.close(fig)
        self.say("![%s](%s)" % (caption, name))
        self.say()

    def save(self):
        with open(os.path.join(self.out, "report.md"), "w") as fh:
            fh.write("\n".join(self.lines) + "\n")


def spectrum_figure(traces, title, note=None, marks=(), ylim=None):
    plt = _plt()
    fig, ax = plt.subplots(figsize=(9.5, 4.2))
    span = max(t[0][-1] for t in traces) - min(t[0][0] for t in traces)
    unit, scale = ("GHz", GHZ) if span > 1.5 * GHZ else ("MHz", MHZ)
    for k, ((f, p, label), c) in enumerate(zip(traces, (C2, C1, C3))):
        fd, pd = peak_trace(f, p)
        ax.plot(fd / scale, pd, color=c, label=label, zorder=5 - k)
    for fm, pm, text in marks:
        ax.annotate(text, (fm / scale, pm), xytext=(0, 9),
                    textcoords="offset points", ha="center", fontsize=8,
                    color=INK, arrowprops=dict(arrowstyle="-", color=AXIS,
                                               lw=0.6))
    ax.set_xlabel("input frequency, %s" % unit)
    ax.set_ylabel("reading, dBm")
    ax.set_title(title)
    lo_, hi_ = ax.get_ylim()
    ax.set_ylim(*(ylim or (lo_, hi_ + (12 if marks else 0))))
    if len(traces) > 1:
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.16),
                  ncol=len(traces))
    if note:
        fig.text(0.125, -0.02, note, fontsize=8, color=INK2, va="top")
    return fig


# --------------------------------------------------------------------- cases

def to_mixer(sa, f):
    """The gain, in dB, from the input connector to the first mixer in the
    path of an input at f."""
    fc = sa.centres(f, f)[0]
    band, st, _, _ = sa.tune(fc)
    g = 0.0
    for s in sa.chains[band].main:
        if not hasattr(s, "part"):
            return g
        g += float(s.part.g(f))
    return None                         # no mixer in this path


def case_budget(sa, rep, a):
    rep.say("## Budget")
    rep.say()
    board = sa.design == "board"
    ifa = ("%g dB" % sa.if_att_db if sa.if_att_db is not None else
           "at each band's trim (%g dB low band, %g dB high band)"
           % (sa.if_trim["L1"], sa.if_trim["H1"]))
    rep.say("Input attenuator %g dB, IF attenuator %s, %s. The first IF "
            "is %.3f GHz (this filter's centre) and the second %g MHz; the "
            "superheterodyne path ends at %.2f GHz."
            % (sa.att_db, ifa,
               ("input buffer %s" if board else "preamps %s")
               % ("in" if sa.preamp else "bypassed"), sa.if1 / GHZ,
               sa.if2 / MHZ, sa.a_top / GHZ))
    rep.say()
    rows = []
    for f in (0.005, 0.1, 0.5, 1.0, 1.5, 2.0, 2.29, 2.6, 3.0, 3.4, 4.0, 4.4,
              5.0, 5.5, 6.0, 6.4):
        if f * GHZ > sa.top:
            continue
        _, s = sa.budget(f * GHZ)
        rows.append(("%.3g" % f, s["band"], "%.1f" % s["gain_to_adc"],
                     "%.1f" % s["nf_friis"], "%.1f" % s["nf_effective"],
                     "%.1f" % s["danl_dbm_hz"], "%+.1f" % s["iip3"],
                     "%+.1f" % s["ip1db"],
                     "%+.1f" % s["adc_full_scale_dbm"],
                     "%.0f" % s["sfdr_db_1hz"]))
    rep.table(["f, GHz", "band", "gain to ADC, dB", "NF (Friis), dB",
               "NF (effective), dB", "noise floor, dBm/Hz", "IIP3, dBm",
               "P1dB in, dBm", "ADC full scale, dBm", "SFDR, dB (1 Hz)"],
              rows)
    if board:
        variants = [(1.0, "as drawn", {}),
                    (1.0, "input buffer in", dict(preamp=True)),
                    (1.0, "IF attenuator 20 dB", dict(if_att_db=20.0)),
                    (1.0, "without the 20 dB amplifier",
                     dict(fixed_lna=False)),
                    (3.0, "as drawn", {}), (0.005, "as drawn", {})]
        rep.say("With the input attenuator at 0 dB (the most sensitive "
                "setting):")
    else:
        variants = [(f, "preamps %s" % ("in" if pre else "bypassed"),
                     dict(preamp=pre))
                    for f, pre in ((0.005, False), (0.1, False), (0.1, True),
                                   (1.0, False), (1.0, True), (2.6, False),
                                   (2.6, True), (4.0, False), (4.0, True),
                                   (6.2, False), (6.2, True))
                    if f * GHZ <= sa.top]
        rep.say("With the input attenuator at 0 dB (the most sensitive "
                "setting), without and with the preamps (a TRF37D73 in the "
                "low band, a PMA3-83LN+ in the high band, each after its "
                "band's first filter):")
    rep.say()
    rows = []
    for f, what, kw in variants:
        s0 = sa.like(att_db=0.0, **kw)
        _, s = s0.budget(f * GHZ)
        gm = to_mixer(s0, f * GHZ)
        rows.append(("%.3g" % f, s["band"], what,
                     "%.1f" % s["nf_effective"],
                     "%.1f" % s["danl_dbm_hz"], "%+.1f" % s["iip3"],
                     "%+.1f" % s["adc_full_scale_dbm"],
                     "-" if gm is None else
                     "%+.1f" % (s["adc_full_scale_dbm"] + gm),
                     "%.2f" % s["noise_at_adc_lsb"],
                     "%.0f" % s["sfdr_db_1hz"]))
    rep.table(["f, GHz", "band", "", "NF (effective), dB",
               "noise floor, dBm/Hz", "IIP3, dBm", "ADC full scale, dBm",
               "first mixer sees then, dBm", "chain noise at the ADC, LSB rms",
               "SFDR, dB (1 Hz)"], rows)
    rep.say("The effective noise figure is what the noise pass finds: it has "
            "the second mixer's image, the LOs' noise and the ADC's, which "
            "the Friis column leaves out. SFDR is 2/3 (IIP3 - noise floor) "
            "in 1 Hz; take 2/3 of 10 log(RBW) off for a wider one. A level 7 "
            "mixer is clean to about -25 dBm and compresses at +1 dBm: "
            "where the ADC's full scale puts more than that on the first "
            "mixer, the mixer limits the analyzer before the ADC does.")
    rep.say()
    lsb, one = dither(sa)
    if lsb < 0.5:
        rep.say("**The ADC is not dithered.** The chain puts %.2f LSB rms of "
                "noise on it, and it wants half an LSB or more: with nothing "
                "larger in the IF band it rests on one code, the noise "
                "floors above are not reached, and a signal alone must be "
                "about %.0f dBm at the input (attenuator %g dB) to move it "
                "by an LSB. About %.0f dB more gain ahead of the ADC would "
                "dither it." % (lsb, one, sa.att_db,
                                 20 * np.log10(0.5 / lsb)))
        rep.say()
    for f in (1.0 * GHZ, 5.0 * GHZ):
        if f > sa.top:
            continue
        rws, s = sa.budget(f)
        rep.say("### Stage by stage at %.1f GHz (band %s)" % (f / GHZ,
                                                             s["band"]))
        rep.say()
        rep.table(["stage", "at, MHz", "gain, dB", "NF, dB", "IIP3, dBm",
                   "gain so far", "NF so far", "IIP3 so far"],
                  [(r["stage"], "%.1f" % (r["f"] / MHZ), "%+.1f" % r["gain"],
                    "%.1f" % r["nf"],
                    "-" if r["iip3"] > 200 else "%+.0f" % r["iip3"],
                    "%+.1f" % r["cum_gain"], "%.1f" % r["cum_nf"],
                    "%+.1f" % r["cum_iip3"]) for r in rws])


def case_cw(sa, rep, a):
    rep.say("## A carrier at 1 GHz, -30 dBm")
    rep.say()
    sig = [Signal(1.0 * GHZ, -30.0)]
    f0, f1 = 0.9 * GHZ, 1.1 * GHZ
    f, p1, _ = sa.sweep(sig, f0, f1, image_reject=False)
    _, p2, _ = sa.sweep(sig, f0, f1, image_reject=True)
    rbw = sa.capture([], 1.0 * GHZ)[2]["enbw"]
    img = 1.0 * GHZ - 2 * sa.if2
    rows = [("carrier", "%.1f" % reading(f, p1, 1.0 * GHZ),
             "%.1f" % reading(f, p2, 1.0 * GHZ)),
            ("image, about %g MHz below" % (2 * sa.if2 / MHZ),
             "%.1f" % reading(f, p1, img, sa.if2),
             "%.1f" % reading(f, p2, img, sa.if2)),
            ("noise floor (median)", floor_text(sa, p1),
             floor_text(sa, p2))]
    for off in (100e3, 300e3):
        n1 = level(f, p1, 1.0 * GHZ + off, 15e3)
        n2 = level(f, p2, 1.0 * GHZ + off, 15e3)
        rows.append(("skirt at +%g kHz (mean)" % (off / 1e3), "%.1f" % n1,
                     "%.1f" % n2))
    rep.table(["reading, dBm (RBW %.1f kHz)" % (rbw / 1e3),
               "one capture per step", "two captures, the lower kept"], rows)
    lo1 = sa.lo1.phase_noise(1.0 * GHZ + sa.if1, 100e3)
    lo2 = sa.lo2.phase_noise(sa.if1 - sa.if2, 100e3)
    rep.say("At 100 kHz the two LOs' phase noise is %.1f and %.1f dBc/Hz "
            "(the synthesizers' datasheet profiles at %.2f and %.2f GHz), which in this "
            "RBW is %.1f dBc: the skirt above."
            % (lo1, lo2, (1.0 * GHZ + sa.if1) / GHZ,
               (sa.if1 - sa.if2) / GHZ,
               10 * np.log10(10 ** (lo1 / 10) + 10 ** (lo2 / 10))
               + 10 * np.log10(rbw)))
    rep.say()
    rep.say("The lower of two readings of noise is 3 dB under either: with "
            "two captures the floor, and any noise-like signal, reads 3 dB "
            "low.")
    rep.say()
    fig = spectrum_figure(
        [(f, p1, "one capture per step"),
         (f, p2, "two captures, the lower kept")],
        "A -30 dBm carrier at 1 GHz",
        marks=[(f[np.abs(f - img) <= sa.if2][np.argmax(
            p1[np.abs(f - img) <= sa.if2])], reading(f, p1, img, sa.if2),
            "image of the second mixer")])
    rep.figure(fig, "cw.png", "A carrier at 1 GHz")

    # close in, with a 64 times longer capture, against the datasheet
    fine = sa.like(nfft=262144)
    fc, pc, info = fine.capture([Signal(1000.2 * MHZ, -15.0)], 1.0 * GHZ)
    off = fc - 1000.2 * MHZ
    car = reading(fc, pc, 1000.2 * MHZ, 2e3)
    dbc = pc - car - 10 * np.log10(info["enbw"])
    plt = _plt()
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    sel = (off > 2e3) & (off < 4e6)
    edges = np.logspace(np.log10(2e3), np.log10(4e6), 60)
    mid, val = [], []
    for e0, e1 in zip(edges[:-1], edges[1:]):
        m = sel & (off >= e0) & (off < e1)
        if m.any():
            mid.append(np.sqrt(e0 * e1))
            val.append(10 * np.log10(np.mean(10 ** (dbc[m] / 10))))
    o = np.logspace(np.log10(2e3), np.log10(4e6), 200)
    model = 10 * np.log10(
        10 ** (sa.lo1.phase_noise(1.0 * GHZ + sa.if1, o) / 10)
        + 10 ** (sa.lo2.phase_noise(sa.if1 - sa.if2, o) / 10))
    ax.semilogx(o, model, color=C2, lw=1.6,
                label="LO1 + LO2, datasheet profile")
    ax.semilogx(mid, val, color=C1, lw=0, marker="o", ms=3.5,
                label="simulated reading")
    ax.set_xlabel("offset from the carrier, Hz")
    ax.set_ylabel("dBc/Hz")
    ax.set_title("Phase noise on a -15 dBm carrier at 1 GHz")
    ax.legend(loc="upper right")
    rep.say("Close in (a 262144-sample capture, RBW %.0f Hz), the reading "
            "follows the two LOs' datasheet profiles until the analyzer's "
            "noise floor takes over:" % info["enbw"])
    rep.say()
    rep.figure(fig, "cw_phase_noise.png", "Phase noise at 1 GHz")


def case_im3(sa, rep, a):
    # as large as the ADC takes with the attenuator at 0 dB
    lv = float(np.floor(sa.like(att_db=0.0).budget(1.0 * GHZ)[1][
        "adc_full_scale_dbm"] - 9.5))
    rep.say("## Two tones, 1 MHz apart, %g dBm each" % lv)
    rep.say()
    f1, f2 = 1000.2 * MHZ, 1001.2 * MHZ
    rows, traces = [], []
    for att in (0.0, 10.0, 20.0):
        s2 = sa.like(att_db=att, nfft=262144)
        f, p, clip = s2.sweep([Signal(f1, lv), Signal(f2, lv)],
                              996 * MHZ, 1006 * MHZ, image_reject=False,
                              workers=1)
        im = max(reading(f, p, 2 * f1 - f2, 1e3),
                 reading(f, p, 2 * f2 - f1, 1e3))
        tone = reading(f, p, f1, 1e3)
        _, s = s2.budget(1.0 * GHZ)
        rows.append(("%g" % att, "%.1f" % tone, "%.1f" % im,
                     "%.1f" % (im - tone), "%.1f" % (2 * (lv - s["iip3"])),
                     "%.1f" % (lv - s["adc_full_scale_dbm"]),
                     floor_text(s2, p)))
        traces.append((f, p, "%g dB" % att))
    rep.table(["input attenuator, dB", "tone reads, dBm", "IM3 reads, dBm",
               "IM3, dBc", "from the budget's IIP3, dBc",
               "each tone at the ADC, dBFS", "floor, dBm"], rows)
    rep.say("With no attenuation the product is the chain's, near the "
            "budget's, whose cascade adds every stage's product in phase. "
            "Each 10 dB of attenuation should take it down 20 dB; what is "
            "left when it does not is the ADC's own distortion, which does "
            "not fall with the level.")
    rep.say()
    fig = spectrum_figure(traces, "Two %g dBm tones 1 MHz apart, by input "
                          "attenuator (RBW 0.3 kHz)" % lv)
    rep.figure(fig, "im3.png", "Two-tone intermodulation")


def case_compression(sa, rep, a):
    rep.say("## Reading against input level (1 GHz, attenuator %g dB)"
            % sa.att_db)
    rep.say()
    levels = np.arange(-50.0, 12.1, 2.0)
    out, clip, loads = [], [], []
    for lv in levels:
        f, p, info = sa.capture([Signal(1000.2 * MHZ, lv)], 1.0 * GHZ)
        out.append(reading(f, p, 1000.2 * MHZ))
        clip.append(info["clipped"])
        loads.append(dict(info["levels"]))
    out = np.array(out)
    err = out - levels
    first_clip = next((lv for lv, c in zip(levels, clip) if c > 0), None)
    comp = next((lv for lv, e in zip(levels, err) if e < -1.0), None)
    _, s = sa.budget(1.0 * GHZ)
    rep.say("The ADC's full scale is %+.1f dBm at the input (budget); the "
            "first clipped sample appears at %s dBm, and the reading is 1 dB "
            "low from %s dBm. The first stage to compress (the budget's "
            "cascade) does so at %+.1f dBm at the input."
            % (s["adc_full_scale_dbm"],
               "%+.0f" % first_clip if first_clip is not None else "beyond +12",
               "%+.0f" % comp if comp is not None else "beyond +12",
               s["ip1db"]))
    rep.say()
    plt = _plt()
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    ax.plot(levels, err, color=C1, lw=1.6, marker="o", ms=3)
    ax.axhline(-1.0, color=AXIS, lw=0.8)
    ax.annotate("-1 dB", (levels[0], -1.0), xytext=(2, 3),
                textcoords="offset points", fontsize=8, color=INK2)
    ax.set_xlabel("input level, dBm")
    ax.set_ylabel("reading - input, dB")
    ax.set_ylim(-12, 2)
    ax.set_title("Compression of a 1 GHz carrier (ADC clipping and the "
                 "mixers)")
    rep.figure(fig, "compression.png", "Compression")


def case_feedthrough(sa, rep, a):
    # a level the input stages take without compressing
    lv = -30.0 if sa.design == "board" else -10.0
    rep.say("## A %g dBm signal on the first IF (%.2f GHz), seen from the "
            "superheterodyne path" % (lv, sa.if1 / GHZ))
    rep.say()
    sig = [Signal(sa.if1 + 1.3 * MHZ, lv, name="IF1 signal")]
    spans = [(0.5 * GHZ, 0.7 * GHZ)]
    if sa.design == "proposal":
        spans.append((2.5 * GHZ, 2.7 * GHZ))
    rows, traces = [], []
    for f0, f1 in spans:
        f, p, clip = sa.sweep(sig, f0, f1, image_reject=False)
        f, p2, _ = sa.sweep(sig, f0, f1, image_reject=True)
        worst = float(p.max())
        fw = float(f[np.argmax(p)])
        fc = sa.centres(f0, f0)[0]
        band, st, _, _ = sa.tune(fc)
        mid = 0.5 * (f0 + f1)
        main = sa.chains[band].main
        first = next(i for i, m in enumerate(main) if not hasattr(m, "part"))
        filt = -sum(float(x.part.g(sa.if1)) - float(x.part.g(mid))
                    for x in main[:first]
                    if "pass" in x.name or "LFCN" in x.name)
        seen = worst > floor_dbm(p) + 12 or dither(sa)[0] < 0.5
        rows.append(("%.1f-%.1f GHz (%s)" % (f0 / GHZ, f1 / GHZ, band),
                     "%.0f" % filt,
                     "%.1f" % worst if seen else "in the noise",
                     "%.0f" % (lv - worst) if seen else
                     "over %.0f" % (lv - floor_dbm(p) - 12),
                     "%.1f" % float(p2.max()),
                     why(sa, sig, fw, worst) if seen else ""))
        traces.append((f, p, "%.1f-%.1f GHz" % (f0 / GHZ, f1 / GHZ)))
    rep.table(["while sweeping", "input filters at the first IF, dB down",
               "reads, dBm", "dB under the signal",
               "with two captures, dBm", "made by"], rows)
    rep.say("What the input filters leave of it goes straight through the "
            "first mixer (its isolation between ports is the rest of the "
            "rejection) and reads at every tuning.")
    rep.say()
    f, p, label = traces[-1]
    fig = spectrum_figure(
        [(f, p, "")], "A %g dBm signal at %.4f GHz during a %s sweep, one "
        "capture per step" % (lv, (sa.if1 + 1.3 * MHZ) / GHZ, label))
    rep.figure(fig, "feedthrough.png", "IF feedthrough")


def case_residuals(sa, rep, a):
    rep.say("## The superheterodyne path with nothing connected")
    rep.say()
    f0, f1 = 20 * MHZ, sa.a_top
    f, p, _ = sa.sweep([], f0, f1, image_reject=False)
    _, p2, _ = sa.sweep([], f0, f1, image_reject=True)
    fl = floor_dbm(p)
    rows = []
    for fs, ps in sorted(spurs(sa, [], f, p), key=lambda x: -x[1])[:25]:
        rows.append(("%.2f" % (fs / MHZ), "%.1f" % ps,
                     "%.1f" % reading(f, p2, fs, 15e3),
                     why(sa, [], fs, ps)))
    rep.say("Noise floor: %s%s. Responses 15 dB or more over their step's "
            "floor:" % (floor_text(sa, p), " dBm (median)"
                        if dither(sa)[0] >= 0.5 else ""))
    rep.say()
    if rows:
        rep.table(["at, MHz", "one capture, dBm", "two captures, dBm",
                   "made by"], rows)
    else:
        rep.say("none.")
        rep.say()
    fig = spectrum_figure(
        [(f, p, "one capture per step"),
         (f, p2, "two captures, the lower kept")],
        "Input terminated: the analyzer's own responses")
    rep.figure(fig, "residuals.png", "Residual responses")


def case_high(sa, rep, a):
    rep.say("## The high band: a carrier at 5 GHz, and a bursting 18 MHz "
            "wide signal at 5.5 GHz")
    rep.say()
    fc = 5.0 * GHZ
    cw = [Signal(fc, -40.0)]
    f, p, _ = sa.sweep(cw, fc - 0.1 * GHZ, fc + 0.1 * GHZ,
                       image_reject=False)
    _, p2, _ = sa.sweep(cw, fc - 0.1 * GHZ, fc + 0.1 * GHZ,
                        image_reject=True)
    img = fc - 2 * sa.if2
    rep.table(["reading, dBm", "one capture per step",
               "two captures, the lower kept"],
              [("carrier, 5 GHz", "%.1f" % reading(f, p, fc),
                "%.1f" % reading(f, p2, fc)),
               ("image, about %g MHz below" % (2 * sa.if2 / MHZ),
                "%.1f" % reading(f, p, img, sa.if2),
                "%.1f" % reading(f, p2, img, sa.if2)),
               ("noise floor", floor_text(sa, p), floor_text(sa, p2))])
    fig = spectrum_figure(
        [(f, p, "one capture per step"),
         (f, p2, "two captures, the lower kept")],
        "A -40 dBm carrier at 5 GHz, high band (no image filter)")
    rep.figure(fig, "high_cw.png", "High band carrier")

    fb, bw, lv = 5.5 * GHZ, 18 * MHZ, -40.0
    burst = [Signal(fb, lv, bw=bw, duty=0.35, name="burst")]
    steady = [Signal(fb, lv, bw=bw, name="steady")]
    f0, f1 = fb - 60 * MHZ, fb + 60 * MHZ
    inrbw = lv - 10 * np.log10(bw / sa.capture([], fb)[2]["enbw"])
    traces, rows = [], []
    for ir, label in ((False, "one capture per step"),
                      (True, "two captures, the lower kept")):
        acc = None
        for k in range(8):                      # eight sweeps, max hold
            f, p, _ = sa.sweep(burst, f0, f1, image_reject=ir, sweep=k)
            acc = p if acc is None else np.maximum(acc, p)
        traces.append((f, acc, label))
        _, ps, _ = sa.sweep(steady, f0, f1, image_reject=ir)
        own = np.abs(f - fb) < 8 * MHZ
        ghost = np.abs(f - (fb - 2 * sa.if2)) < 5 * MHZ
        rows.append((label, "%.1f" % level(f, ps, fb, 8 * MHZ),
                     "%.1f" % np.median(acc[own]),
                     "%.0f %%" % (100 * np.mean(acc[own] > inrbw - 10)),
                     "%.1f" % np.median(acc[ghost])))
    rep.say("A noise-like signal %g MHz wide, %g dBm in total, is %.1f dBm "
            "in this RBW. Steady, and then on for 35 %% of the captures "
            "(each capture is 0.1 ms), max hold over eight sweeps:"
            % (bw / MHZ, lv, inrbw))
    rep.say()
    rep.table(["", "steady: reads, dBm", "bursting: reads (median), dBm",
               "bursting: share of its band shown", "%g MHz below: reads, "
               "dBm" % (2 * sa.if2 / MHZ)], rows)
    rep.say("One capture per step shows the signal and its image side by "
            "side. Keeping the lower of two captures removes the image, but "
            "a step shows a bursting signal only when both of its captures "
            "caught it: the signal is shown in pieces, and low.")
    rep.say()
    fig = spectrum_figure(traces, "A bursting 18 MHz wide signal at 5.5 "
                          "GHz, max hold of 8 sweeps")
    rep.figure(fig, "high_burst.png", "High band burst")


def spurs(sa, signals, f, p, over=15.0, guard=3 * MHZ):
    """The readings that stand `over` dB above their 10 MHz step's median
    and are not within `guard` of a signal: (f, dBm) of each step's peak."""
    n = int(round(sa.step / (f[1] - f[0])))
    out = []
    lsb, one = dither(sa)
    least = one - 25.0 if lsb < 0.5 else -999.0
    for i in range(0, f.size - n + 1, n):
        sf, sp = f[i:i + n], p[i:i + n].copy()
        med = max(np.median(sp), least)
        for s in signals:
            sp[np.abs(sf - s.f) < guard + s.bw / 2] = -999.0
        j = int(np.argmax(sp))
        if sp[j] > med + over:
            out.append((float(sf[j]), float(sp[j])))
    return out


def case_full(sa, rep, a):
    f0 = 0.1 * MHZ
    rep.say("## %g MHz to %.2f GHz" % (f0 / MHZ, sa.top / GHZ))
    rep.say()
    sig = [Signal(100.3 * MHZ, -45.0), Signal(915.2 * MHZ, -35.0),
           Signal(1575.4 * MHZ, -60.0), Signal(2.4401 * GHZ, -40.0),
           Signal(5.2003 * GHZ, -45.0), Signal(6.2003 * GHZ, -45.0)]
    sig.insert(0, Signal(3.3 * MHZ, -45.0))
    t0 = time.time()
    f, p1, _ = sa.sweep(sig, f0, sa.top, image_reject=False)
    _, p, clip = sa.sweep(sig, f0, sa.top, image_reject=True)
    took = time.time() - t0
    seen = [s for s in sig if s.f <= sa.top]
    rows = [("%.1f" % (s.f / MHZ), "%.1f" % s.dbm,
             "%.1f" % reading(f, p, s.f) if s.f <= sa.top
             else "above the range") for s in sig]
    rep.table(["signal, MHz", "level, dBm", "reads, dBm"], rows)
    found = sorted(spurs(sa, seen, f, p1), key=lambda x: -x[1])
    left = spurs(sa, seen, f, p)
    rows = []
    for fs, ps in found[:16]:
        rows.append(("%.2f" % (fs / MHZ), "%.1f" % ps,
                     "%.1f" % reading(f, p, fs, 15e3),
                     why(sa, sig, fs, ps)))
    rep.say("Readings 15 dB or more over the local floor that are not the "
            "signals: %d with one capture per step, %d with two (%.1f %% "
            "of the ADC's samples clipped at worst)."
            % (len(found), len(left), 100 * clip))
    rep.say()
    if rows:
        rep.table(["at, MHz", "one capture, dBm", "two captures, dBm",
                   "made by"], rows)
    rep.say("%d captures of %d samples, %.0f s of simulation."
            % (3 * len(sa.centres(f0, sa.top)), sa.nfft, took))
    rep.say()
    fig = spectrum_figure([(f, p1, "one capture per step"),
                           (f, p, "two captures, the lower kept")],
                          "%d signals, %g MHz to %.2f GHz"
                          % (len(sig), f0 / MHZ, sa.top / GHZ),
                          marks=[(s.f, reading(f, p, s.f),
                                  "%.0f dBm" % s.dbm) for s in seen])
    rep.figure(fig, "full.png", "Full sweep")


def case_strong(sa, rep, a):
    lv, fs = 0.0, 915.2 * MHZ
    att = 31.5 if sa.design == "board" else 31.75      # all there is
    rep.say("## One strong signal: %g dBm at %.1f MHz, attenuator %g dB"
            % (lv, fs / MHZ, att))
    rep.say()
    s2 = sa.like(att_db=att)
    f0 = 0.1 * MHZ
    sig = [Signal(fs, lv)]
    f, p1, _ = s2.sweep(sig, f0, s2.top, image_reject=False)
    _, p, clip = s2.sweep(sig, f0, s2.top, image_reject=True)
    found = sorted(spurs(s2, sig, f, p1), key=lambda x: -x[1])
    left = sorted(spurs(s2, sig, f, p), key=lambda x: -x[1])
    rep.say("The first mixer sees %.0f dBm. The signal reads %.1f dBm. Other "
            "readings 15 dB or more over the local floor: %d with one "
            "capture per step, %d with two (%.1f %% of the ADC's samples "
            "clipped at worst)." % (
                lv + to_mixer(s2, fs), reading(f, p, fs), len(found),
                len(left), 100 * clip))
    rep.say()
    rows = []
    kept = {round(x[0] / 1e5) for x in left}
    for fx, px in found[:20]:
        both = reading(f, p, fx, 15e3)
        rows.append(("%.2f" % (fx / MHZ), "%.1f" % px, why(s2, sig, fx, px),
                     "%.1f" % both, why(s2, sig, fx, both, shifted=True)
                     if round(fx / 1e5) in kept else ""))
    if rows:
        rep.table(["at, MHz", "one capture, dBm", "made by",
                   "two captures, dBm", "and in the second capture by"],
                  rows)
    rep.say("`1LO2-1[1LO1-1[x]]` is the plain conversion of x: where it is "
            "not at x it is the second mixer's image. A reading at a whole "
            "multiple of the signal's frequency is the analyzer's own "
            "harmonic distortion.")
    rep.say()
    fig = spectrum_figure([(f, p1, "one capture per step"),
                           (f, p, "two captures, the lower kept")],
                          "A %g dBm signal at %.1f MHz, attenuator %g dB"
                          % (lv, fs / MHZ, att))
    rep.figure(fig, "strong.png", "One strong signal")


def case_direct(sa, rep, a):
    rep.say("## The direct-sample path: 0.1 to 15 MHz")
    rep.say()
    sig = [Signal(3.3 * MHZ, -40.0), Signal(27.2 * MHZ, -40.0)]
    f, p, clip = sa.sweep(sig, 0.1 * MHZ, 15 * MHZ, workers=1)
    alias = sa.adc.fs - 27.2 * MHZ
    _, s = sa.budget(5 * MHZ)
    rep.table(["", "reads, dBm"],
              [("3.3 MHz at -40 dBm", "%.1f" % reading(f, p, 3.3 * MHZ)),
               ("27.2 MHz at -40 dBm, folded to %.1f MHz" % (alias / MHZ),
                "%.1f" % reading(f, p, alias)),
               ("noise floor (median)", floor_text(sa, p))])
    rep.say("Only low-pass filtering stands between this path and the ADC, "
            "so a signal between 22 and 38 MHz folds into it, less what "
            "those filters take off. Noise figure %.1f dB, ADC full "
            "scale %+.1f dBm at the input with this attenuation."
            % (s["nf_effective"], s["adc_full_scale_dbm"]))
    rep.say()
    fig = spectrum_figure([(f, p, "")], "The direct-sample path with "
                          "signals at 3.3 and 27.2 MHz")
    rep.figure(fig, "direct.png", "Direct-sample path")


def case_compare(sa, rep, a):
    """The board's chain against the proposal's, on the same tests."""
    rep.say("## The board's chain against the proposal's")
    rep.say()
    kw = dict(seed=sa.seed)
    cols = [("board, as drawn", dict(design="board")),
            ("proposal, preamp bypassed", dict(design="proposal")),
            ("proposal, preamp in", dict(design="proposal", preamp=True))]
    f1 = 1.0 * GHZ
    res = []
    for name, d in cols:
        d = dict(kw, **d)
        s0 = Analyzer(att_db=0.0, **d)
        _, b = s0.budget(f1)
        gm0 = to_mixer(s0, f1)
        amax = 31.5 if d["design"] == "board" else 31.75
        smax = Analyzer(att_db=amax, **d)
        gmx = to_mixer(smax, f1)
        _, bx = smax.budget(f1)
        rbw = 10 * np.log10(19.6e3)
        least = (b["danl_dbm_hz"] + rbw if b["noise_at_adc_lsb"] >= 0.5
                 else b["one_lsb_dbm"])
        # a signal on the first IF, and two above the input low-pass that
        # are 1050 MHz apart: what each makes at the second mixer's output,
        # referred to the input (no ADC in it)
        sig = [Signal(s0.if1 + 1.3 * MHZ, -30.0)]
        ift = [x for x in s0.explain(sig, 0.6 * GHZ - 1.3 * MHZ, span=30e3)
               if x[1] is not None]
        oob = [Signal(3.9001 * GHZ, -30.0), Signal(4.9503 * GHZ, -30.0)]
        im2 = [x for x in s0.explain(oob, 1050.2 * MHZ, span=30e3)
               if x[1] is not None]
        res.append([
            "%.2f GHz" % (s0.top / 1e9),
            "%.1f" % b["nf_friis"],
            "%.1f" % b["nf_effective"], "%.1f" % b["danl_dbm_hz"],
            "%.2f" % b["noise_at_adc_lsb"],
            "%.0f%s" % (least, "" if b["noise_at_adc_lsb"] >= 0.5
                        else " (one LSB)"),
            "%+.1f" % b["iip3"],
            "%+.1f" % b["adc_full_scale_dbm"],
            "%+.1f" % (b["adc_full_scale_dbm"] + gm0),
            "%+.1f" % (-25.0 - gmx),
            "%+.1f" % min(bx["adc_full_scale_dbm"], 1.0 - gmx),
            "%.0f" % (-30.0 - ift[0][1]) if ift else "over 100",
            "%.0f" % im2[0][1] if im2 and im2[0][1] > -130 else "nothing"])
    names = ["highest frequency",
             "noise figure of the chain alone, dB",
             "noise figure with the image and the ADC, dB",
             "noise floor, dBm/Hz",
             "chain noise at the ADC, LSB rms (0.5 or more dithers it)",
             "smallest signal seen alone in a 19.6 kHz RBW, dBm",
             "IIP3, dBm",
             "ADC full scale at the input, dBm",
             "level at the first mixer when the ADC is at full scale, dBm",
             "largest input that keeps the first mixer at -25 dBm "
             "(most attenuation), dBm",
             "largest input before the ADC clips or the mixer compresses, "
             "dBm",
             "a signal on the first IF reads this many dB down",
             "two -30 dBm signals at 3.90 and 4.95 GHz make, at 1050 MHz, "
             "dBm"]
    rep.table([""] + [c[0] for c in cols],
              [[n] + [r[i] for r in res] for i, n in enumerate(names)])
    rep.say("At 1 GHz with the input attenuator at 0 dB, except the two "
            "largest-input rows. The mixer is a level 7 part: clean to about "
            "-25 dBm, 1 dB compressed at +1 dBm. The last two rows are what "
            "the chain makes ahead of the ADC, referred to the input.")
    rep.say()


# the cases that only one of the designs has the hardware for
ONLY = dict(high="proposal")

CASES = dict(compare=case_compare, budget=case_budget, cw=case_cw,
             im3=case_im3, direct=case_direct,
             compression=case_compression, feedthrough=case_feedthrough,
             residuals=case_residuals, high=case_high, full=case_full,
             strong=case_strong)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("cases", nargs="*", help="default: all of them")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--design", choices=("board", "proposal"),
                    default="board")
    ap.add_argument("--att", type=float, default=10.0)
    ap.add_argument("--if-att", type=float, default=None)
    ap.add_argument("--preamp", action="store_true")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--lo1", choices=("lmx2582", "lmx2572"), default=None)
    ap.add_argument("--lo2", choices=("lmx2582", "lmx2572"), default=None)
    ap.add_argument("--pads", type=float, nargs=2, default=(3.0, 6.0),
                    metavar="DB", help="proposal: the pads at the first "
                    "mixer's IF port and after the IF1 amplifier")
    ap.add_argument("--no-lna", action="store_true",
                    help="board: without its 20 dB amplifier")
    ap.add_argument("--out", default=os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "out"))
    a = ap.parse_args(argv)
    if a.list:
        print("\n".join(CASES))
        return 0
    bad = [c for c in a.cases if c not in CASES]
    if bad:
        ap.error("no such case: %s (--list)" % ", ".join(bad))
    sa = Analyzer(design=a.design,
                  lo1=getattr(lo, a.lo1)() if a.lo1 else None,
                  lo2=getattr(lo, a.lo2)() if a.lo2 else None,
                  att_db=a.att, if_att_db=a.if_att, preamp=a.preamp,
                  seed=a.seed, pad1_db=a.pads[0],
                  pad2_db=a.pads[1], fixed_lna=not a.no_lna)
    rep = Report(a.out)
    rep.say("# Spectrum analyzer simulation: the %s"
            % ("board's chain" if a.design == "board" else "proposal"))
    rep.say()
    rep.say("LO1 %s, LO2 %s, two SIM-83+, 40 MSPS %s, %d-point captures."
            % (sa.lo1.name, sa.lo2.name, sa.adc.name, sa.nfft))
    rep.say()
    for name in (a.cases or [c for c in CASES
                             if ONLY.get(c, a.design) == a.design]):
        if ONLY.get(name, a.design) != a.design:
            print("[%s: not a case of the %s]" % (name, a.design),
                  file=sys.stderr)
            continue
        t0 = time.time()
        CASES[name](sa, rep, a)
        print("[%s: %.0f s]" % (name, time.time() - t0), file=sys.stderr)
    rep.say("## Where each part's numbers come from")
    rep.say()
    rep.table(["part", "source"], parts.provenance(sa.all_parts()))
    rep.save()
    print("wrote %s" % os.path.join(a.out, "report.md"), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
