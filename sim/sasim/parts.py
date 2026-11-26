"""
The parts of the analyzer, each as a small-signal gain against frequency, a
noise figure, and its non-linearity (intercepts, compression), with where every
number comes from.

A part's S-parameters come from, in this order:

    vendor/<PART>.s2p    the manufacturer's own Touchstone file, if you put
                         it there (see vendor/README.md: they cannot be
                         fetched or redistributed from here)
    data/<name>.s2p      the printed filters, synthesised by dfsynth and solved
                         by kicad2ems's mom25d (make_filters.sh)
    a datasheet model    the datasheet's own table, interpolated

`Part.source` says which one a run used; `provenance()` prints them all.
"""

import os
from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
VENDOR = os.path.join(ROOT, "vendor")

INF = float("inf")
GHZ = 1e9
MHZ = 1e6


def table(points, log=False):
    """dB against Hz, linear between the points and held past the ends."""
    f = np.array([p[0] for p in points], float)
    v = np.array([p[1] for p in points], float)
    if log:
        f = np.log10(np.maximum(f, 1.0))
        return lambda x: np.interp(
            np.log10(np.maximum(np.asarray(x, float), 1.0)), f, v)
    return lambda x: np.interp(np.asarray(x, float), f, v)


def const(db):
    return lambda x: np.full(np.shape(x), float(db))


def touchstone(path):
    """(f Hz, |S21| dB, |S11| dB) of a 2-port Touchstone file."""
    import skrf
    n = skrf.Network(path)
    s21 = 20 * np.log10(np.maximum(np.abs(n.s[:, 1, 0]), 1e-12))
    s11 = 20 * np.log10(np.maximum(np.abs(n.s[:, 0, 0]), 1e-12))
    return n.f, s21, s11


@dataclass
class Part:
    name: str
    source: str
    gain: Callable                      # |S21| dB at f (Hz)
    nf: Optional[Callable] = None       # dB; None: passive, NF = its loss
    iip3: float = INF                   # dBm at the input
    iip2: float = INF
    ip1db: float = INF                  # input 1 dB compression, dBm
    oip3: float = INF                   # amplifiers: at the output, and the
    oip2: float = INF                   # input values follow from the gain
    op1db: float = INF
    s2p: Optional[str] = None           # the file its gain came from

    def g(self, f):
        return self.gain(f)

    def noise_figure(self, f):
        if self.nf is None:
            return np.maximum(-self.gain(f), 0.0)
        return self.nf(f)

    def in_ip3(self, f):
        if self.oip3 < INF:
            return self.oip3 - float(np.mean(self.gain(f)))
        return self.iip3

    def in_ip2(self, f):
        if self.oip2 < INF:
            return self.oip2 - float(np.mean(self.gain(f)))
        return self.iip2

    def in_p1db(self, f):
        if self.op1db < INF:
            return self.op1db + 1.0 - float(np.mean(self.gain(f)))
        return self.ip1db


def _from_file(name, part_no, fallback, fallback_source, **kw):
    """The vendor's S-parameters when vendor/<part_no>.s2p is there, else
    the datasheet model."""
    for ext in (".s2p", ".S2P"):
        path = os.path.join(VENDOR, part_no + ext)
        if os.path.exists(path):
            f, s21, _ = touchstone(path)
            return Part(name, "vendor S-parameters: vendor/%s%s (%.3g-%.3g "
                        "GHz, held past the ends)" % (part_no, ext, f[0] / GHZ,
                                                      f[-1] / GHZ),
                        lambda x, f=f, s=s21: np.interp(x, f, s), s2p=path,
                        **kw)
    return Part(name, fallback_source, fallback, **kw)


def em_filter(name, filename, what):
    """A printed filter: dfsynth's layout, solved by mom25d."""
    path = os.path.join(DATA, filename)
    f, s21, _ = touchstone(path)
    return Part(name, "EM simulation (kicad2ems mom25d) of dfsynth's layout: "
                "data/%s, %s" % (filename, what),
                lambda x, f=f, s=s21: np.interp(x, f, s), s2p=path)


# ---------------------------------------------------------------- passives

def pad(db, name=None):
    return Part(name or "%g dB pad" % db, "resistive pad (exact)", const(-db))


def dc_block_limiter():
    return Part("DC block + limiter", "assumed 0.3 dB (no part chosen)",
                const(-0.3))


def pe43711(att_db=0.0, name="PE43711 DSA"):
    """pSemi PE43711 7-bit step attenuator, 9 kHz-6 GHz.
    Datasheet DOC-84940-8 table 3: insertion loss 1.3 / 1.6 / 1.9 / 2.4 dB
    typical in 9k-1G / 1-2.2G / 2.2-4G / 4-6G, IIP3 +57 dBm at 4 GHz, input
    0.1 dB compression +31 dBm."""
    att = round(float(att_db) * 4) / 4
    if not 0 <= att <= 31.75:
        raise ValueError("PE43711: 0 to 31.75 dB")
    il = table([(0, 1.3), (0.5 * GHZ, 1.3), (1.6 * GHZ, 1.6), (3.1 * GHZ, 1.9),
                (5.0 * GHZ, 2.4), (6.0 * GHZ, 2.6), (9.0 * GHZ, 4.0)])
    p = _from_file(name, "PE43711", lambda f: -il(f),
                   "pSemi datasheet DOC-84940 table 3 (typical insertion "
                   "loss by band; past 6 GHz assumed)",
                   iip3=57.0, iip2=100.0, ip1db=33.0)
    base = p.gain
    p.gain = lambda f: base(f) - att
    p.name = "%s (%g dB)" % (name, att)
    return p


def pe43704(att_db=0.0, name="PE43704 DSA"):
    """pSemi PE43704 7-bit step attenuator, 9 kHz-8 GHz: the proposal's
    input attenuator, because the board's BDA4601 ends at 4 GHz.  Datasheet
    DOC-51214 tables 3 and 4: insertion loss 1.3 / 1.7 / 2.4 / 2.5 dB
    typical in 9k-2G / 2-4G / 4-6G / 6-7G, IIP3 +61 dBm, input 1 dB
    compression +34 dBm; 0.25 dB steps to 6 GHz, 0.5 dB to 7 GHz."""
    att = round(float(att_db) * 4) / 4
    if not 0 <= att <= 31.75:
        raise ValueError("PE43704: 0 to 31.75 dB")
    il = table([(0, 1.3), (1.0 * GHZ, 1.3), (3.0 * GHZ, 1.7),
                (5.0 * GHZ, 2.4), (6.5 * GHZ, 2.5), (8.0 * GHZ, 3.0),
                (12 * GHZ, 5.0)])
    p = _from_file(name, "PE43704", lambda f: -il(f),
                   "pSemi datasheet DOC-51214 tables 3-4 (typical insertion "
                   "loss by band, IIP3, compression); past 7 GHz assumed",
                   iip3=61.0, iip2=100.0, ip1db=34.0)
    base = p.gain
    p.gain = lambda f: base(f) - att
    p.name = "%s (%g dB)" % (name, att)
    return p


def pe42540(state="on", name="PE42540 switch"):
    """pSemi PE42540 SP4T, 10 Hz-8 GHz.  Datasheet table: insertion loss
    0.7 / 0.8 / 1.0 / 1.1 / 1.2 dB at LF / 3 / 6 / 7.5 / 8 GHz; RFC-RFx
    isolation 84 / 45 / 33 / 29 / 27 dB typical; IIP3 +58, IIP2 +100,
    P1dB +33 dBm."""
    il = table([(0, 0.7), (3 * GHZ, 0.8), (6 * GHZ, 1.0), (7.5 * GHZ, 1.1),
                (8 * GHZ, 1.2), (12 * GHZ, 2.5)])
    iso = table([(1e4, 84), (3 * GHZ, 45), (6 * GHZ, 33), (7.5 * GHZ, 29),
                 (8 * GHZ, 27), (12 * GHZ, 20)])
    src = "pSemi PE42540 datasheet (typical %s; past 8 GHz assumed)"
    if state == "on":
        return _from_file(name, "PE42540", lambda f: -il(f),
                          src % "insertion loss", iip3=58.0, iip2=100.0,
                          ip1db=33.0)
    return Part(name + " (off path)", src % "RFC-RFx isolation",
                lambda f: -iso(f))


def lfcn2250():
    """Mini-Circuits LFCN-2250+ LTCC low-pass.  No file could be fetched
    (minicircuits.com refuses scripted downloads), so this is the datasheet's
    specification points: pass band DC-2250 MHz (1.2 dB), 3 dB near 2575, 20 dB
    at 2900, 30 dB over 3000-5000 MHz.  These are limits, not the typical
    curve, which is deeper: the model is the conservative one.  Past 5 GHz
    the datasheet gives nothing here and 20 falling to 15 dB is assumed
    (LTCC low-passes re-enter)."""
    loss = table([(0, 0.2), (1.5 * GHZ, 0.5), (2.25 * GHZ, 1.0),
                  (2.575 * GHZ, 3.0), (2.9 * GHZ, 20.0), (3.0 * GHZ, 30.0),
                  (5.0 * GHZ, 30.0), (6.5 * GHZ, 20.0), (20 * GHZ, 15.0)])
    return _from_file("LFCN-2250+", "LFCN-2250+", lambda f: -loss(f),
                      "datasheet specification points (LFCN-2250D+ table, "
                      "read from a search result); past 5 GHz assumed")


# -------------------------------------------------------------- amplifiers

def pma3_83ln(name="PMA3-83LN+"):
    """Mini-Circuits PMA3-83LN+ 0.5-8 GHz LNA.  Datasheet figures (read from
    search results, the datasheet itself could not be fetched): NF 1.3 dB,
    OIP3 +35 dBm and P1dB +20.7 dBm at 2 GHz and 6 V, gain about 21 dB with
    +/-0.9 dB flatness over 0.5-7 GHz.  The slopes against frequency and the
    response outside 0.5-8 GHz are assumed."""
    gain = table([(0.02 * GHZ, 5), (0.1 * GHZ, 14), (0.3 * GHZ, 19),
                  (0.5 * GHZ, 21), (2 * GHZ, 21.3), (5 * GHZ, 20.6),
                  (7 * GHZ, 20), (8 * GHZ, 19), (10 * GHZ, 15),
                  (14 * GHZ, 5)], log=True)
    nf = table([(0.1 * GHZ, 2.5), (0.5 * GHZ, 1.5), (2 * GHZ, 1.3),
                (4 * GHZ, 1.6), (6 * GHZ, 2.0), (8 * GHZ, 2.5)])
    return _from_file(name, "PMA3-83LN+", gain,
                      "datasheet figures at 2 GHz (via search results); "
                      "frequency slopes assumed", nf=nf, oip3=35.0, oip2=50.0,
                      op1db=20.7)


def trf37d73(name="TRF37D73"):
    """TI TRF37D73 gain block, 1 MHz-6 GHz: the low band's preamp, because
    it covers all of it (the PMA3-83LN+ starts at 0.5 GHz).  Datasheet
    SLASE43 table 6.5: gain 22 / 19.5 / 18 / 15.5 / 13 / 10 dB at 0.4 / 2 / 3
    / 4 / 5 / 6 GHz, and at 2 GHz NF 3.25 dB, OIP3 +27.5 dBm, output P1dB
    +16.5 dBm.  Assumed: the gain under 400 MHz (flat: it depends on the
    bias inductor and the blocking capacitors), the noise figure away from
    2 GHz (flat), and OIP2 +45 dBm (the datasheet gives none)."""
    gain = table([(1e6, 22.0), (0.4 * GHZ, 22.0), (2 * GHZ, 19.5),
                  (3 * GHZ, 18.0), (4 * GHZ, 15.5), (5 * GHZ, 13.0),
                  (6 * GHZ, 10.0), (9 * GHZ, 2.0), (14 * GHZ, -8.0)])
    return _from_file(name, "TRF37D73", gain,
                      "TI datasheet SLASE43 table 6.5 (gain by frequency; "
                      "NF, OIP3, P1dB at 2 GHz); OIP2 assumed", nf=const(3.25),
                      oip3=27.5, oip2=45.0, op1db=16.5)


def amplifier_off(name="PMA3-83LN+ (unpowered)", iso_db=20.0):
    return Part(name, "assumed %g dB through an unpowered LNA" % iso_db,
                const(-iso_db))


# ------------------------------------------------------------- IF2 (10 MHz)

def diplexer_lp(fc=30 * MHZ, name=None):
    """The low-pass arm of a third-order constant-resistance diplexer at the
    second mixer's IF port (the high-pass arm ends in 50 ohm, so the mixer
    sees 50 ohm at its sum products): a Butterworth response."""
    return Part(name or "IF2 diplexer (LP arm, %g MHz)" % (fc / MHZ),
                "ideal 3rd-order Butterworth, 0.3 dB loss assumed",
                lambda f: -0.3 - 10 * np.log10(
                    1 + (np.asarray(f, float) / fc) ** 6))


def lmh6629(gain_db=20.0, name="LMH6629 gain stage"):
    """TI LMH6629 at Av = 10 with a 50 ohm input termination.  Datasheet
    SNOSB18: NF 8.0 dB (RS = RT = 50 ohm); HD2 -70 dBc and HD3 -82 dBc at
    10 MHz and 2 Vpp, which is +10 dBm in this model's terms (the power its
    output voltage would be in 50 ohm), so OIP2 = 10 + 70 - 6 = +74 dBm and
    OIP3 = 10 + (82 - 9.5) / 2 = +46 dBm.  (Its two-tone figure, +31 dBm at
    25 MHz, is at a higher frequency and a different load: the 10 MHz
    harmonic figures are used.)  Its output swings to 0.8 V from the rails:
    3.4 Vpp on 5 V, +14.6 dBm.  The closed-loop bandwidth at this gain
    (90 MHz, one pole) is assumed."""
    return Part(name, "TI datasheet SNOSB18 (NF, HD2 and HD3 at 10 MHz, "
                "swing); bandwidth at Av=10 assumed",
                lambda f: gain_db - 10 * np.log10(
                    1 + (np.asarray(f, float) / (90 * MHZ)) ** 2),
                nf=const(8.0), oip3=46.0, oip2=74.0, op1db=12.6)


def antialias(fc=16.5 * MHZ, order=7, ripple=0.1, stop=70.0, loss=1.0):
    """The anti-alias low-pass in front of the ADC: an elliptic LC ladder,
    0.1 dB ripple, 70 dB stop band (from 1.46 fc at order 7, 1.23 fc at
    order 9).  Its response is the ideal prototype's (scipy.signal.ellip),
    with 1 dB for the inductors' Q."""
    from scipy import signal
    b, a = signal.ellip(order, ripple, stop, 2 * np.pi * fc, analog=True)

    def gain(f):
        _, h = signal.freqs(b, a, 2 * np.pi * np.atleast_1d(
            np.asarray(f, float)))
        g = 20 * np.log10(np.maximum(np.abs(h), 1e-9)) - loss
        return g.reshape(np.shape(f))
    return Part("anti-alias LPF (elliptic N=%d, %.1f MHz)" % (order, fc / MHZ),
                "ideal elliptic prototype, %g dB loss assumed" % loss, gain)


def ths4541(name="THS4541 ADC driver", gain_db=6.0):
    """TI THS4541 fully differential driver, 2 V/V from a matched 50 ohm
    input.  Datasheet SLOS375: HD2 -95 dBc and HD3 -90 dBc at 10 MHz and 2
    Vpp, so (in 50 ohm terms, +10 dBm) OIP2 = +99 dBm and OIP3 = +50 dBm.
    Its noise in this matched circuit is taken as a 20 dB noise figure
    (2.2 nV/rtHz and the resistors: an estimate), which the 37 dB in front of
    it makes irrelevant."""
    return Part(name, "TI datasheet SLOS375 (HD2, HD3 at 10 MHz); noise "
                "figure estimated", const(gain_db), nf=const(20.0), oip3=50.0,
                oip2=99.0, op1db=22.0)


# ------------------------------------------ the board's parts (docs/, .sch)

def bda4601(att_db=0.0, name="BDA4601 DSA"):
    """BeRex BDA4601 6-bit step attenuator, 1 MHz-4 GHz, 31.5 dB in 0.5 dB
    steps.  Its datasheet could not be fetched: the insertion loss (0.8 to
    2.3 dB across the band) is from a distributor's summary, read from a
    search result, and its IIP3 (+50 dBm) and compression (+30 dBm) are
    assumed."""
    att = round(float(att_db) * 2) / 2
    if not 0 <= att <= 31.5:
        raise ValueError("BDA4601: 0 to 31.5 dB")
    il = table([(0, 0.8), (4 * GHZ, 2.3), (6 * GHZ, 4.0), (9 * GHZ, 7.0)])
    p = _from_file(name, "BDA4601", lambda f: -il(f),
                   "insertion loss 0.8-2.3 dB over 1 MHz-4 GHz (a "
                   "distributor's summary, via a search result); IIP3 and "
                   "compression assumed", iip3=50.0, iip2=95.0, ip1db=30.0)
    base = p.gain
    p.gain = lambda f: base(f) - att
    p.name = "%s (%g dB)" % (name, att)
    return p


def if_attenuator(att_db=0.0, top=20.0, name="IF attenuator"):
    """The board's 0-20 dB IF attenuator: no part is named, so 1.3 dB of
    insertion loss and no distortion are assumed."""
    if not 0 <= att_db <= top:
        raise ValueError("%s: 0 to %g dB" % (name, top))
    return Part("%s (%g dB)" % (name, att_db), "assumed (no part named): "
                "1.3 dB insertion loss", const(-1.3 - att_db))


def gain_block(name, gain_db, nf_db, oip3, op1db, oip2=INF, fmax=8 * GHZ):
    """An amplifier the block diagram gives only a gain for: that gain, flat
    to fmax and falling 12 dB an octave above, with assumed noise and
    linearity."""
    def gain(f):
        f = np.maximum(np.asarray(f, float), 1.0)
        return gain_db - 10 * np.log10(1 + (f / fmax) ** 4)
    return Part(name, "assumed (the block diagram gives %g dB and no part): "
                "NF %g dB, OIP3 %+g dBm" % (gain_db, nf_db, oip3), gain,
                nf=const(nf_db), oip3=oip3, oip2=oip2, op1db=op1db)


def lc_bandpass(f1, f2, order=5, ripple=0.1, loss=1.0, name=None):
    """An LC band-pass the block diagram gives only its band for: the ideal
    Chebyshev prototype of that band (scipy.signal.cheby1), with a flat loss
    for the inductors' Q."""
    from scipy import signal
    b, a = signal.cheby1(order, ripple, [2 * np.pi * f1, 2 * np.pi * f2],
                         btype="bandpass", analog=True)

    def gain(f):
        w = 2 * np.pi * np.maximum(np.atleast_1d(np.asarray(f, float)), 1.0)
        _, h = signal.freqs(b, a, w)
        g = 20 * np.log10(np.maximum(np.abs(h), 1e-9)) - loss
        return g.reshape(np.shape(f))
    return Part(name or "band-pass %g-%g MHz (Chebyshev N=%d)"
                % (f1 / MHZ, f2 / MHZ, order),
                "assumed (the block diagram gives the band only): ideal "
                "Chebyshev prototype, %g dB loss" % loss, gain)


def adc_sd9609_40():
    """The board's SD9609-40, a 10 bit 40 MSPS converter, taken to be an
    equivalent of Analog Devices' AD9609-40 (no datasheet was found for the
    SD part).  AD9609 figures, read from a search result: SNR 61.5 dBFS and
    SFDR 75 dBc at 9.7 MHz.  Assumed: 2 Vpp differential full scale, INL
    0.3 LSB, DNL 0.15 LSB, aperture jitter 0.2 ps, HD2 -80 dBc."""
    return Adc(name="SD9609-40 (as an AD9609-40)",
               source="AD9609 figures via a search result (SNR, SFDR); INL, "
               "DNL, jitter and the full scale assumed",
               bits=10, snr_db=61.5, snr_ref_dbfs=0.0, hd2_dbc=-80.0,
               hd3_dbc=-75.0,
               inl_lsb=0.3, dnl_lsb=0.15, jitter_s=0.2e-12,
               fs_dbm_at_driver_input=10.0)


@dataclass
class Adc:
    """TI ADC12040, 12 bit 40 MSPS.  Datasheet SNAS122: SNR 69.5 dB and
    SFDR 84 dB at 10 MHz and -0.5 dBFS, THD -80 dB, INL +/-0.7 LSB, DNL
    +/-0.4 LSB, aperture jitter 1.2 ps rms, full-power bandwidth 100 MHz,
    4 Vpp differential full scale at VREF = 2 V.  The shape of the INL is
    synthetic (three slow sinusoids and a random walk of those sizes)."""
    name: str = "ADC12040"
    source: str = ("TI datasheet SNAS122 (SNR, THD, INL, DNL, jitter); INL "
                   "shape synthetic")
    bits: int = 12
    fs: float = 40e6
    snr_db: float = 69.5
    snr_ref_dbfs: float = -0.5          # the input level the SNR is against
    hd2_dbc: float = -86.0
    hd3_dbc: float = -84.0
    inl_lsb: float = 0.7
    dnl_lsb: float = 0.4
    jitter_s: float = 1.2e-12
    clock_jitter_s: float = 1.0e-12     # the 40 MHz oscillator (assumed)
    # the power, at the driver's 50 ohm input, of a full-scale sine: the
    # driver's 2 V/V makes 2 Vpp there the ADC's 4 Vpp
    fs_dbm_at_driver_input: float = 10.0


def provenance(parts):
    seen, rows = set(), []
    for p in parts:
        if p.name in seen:
            continue
        seen.add(p.name)
        rows.append((p.name, p.source))
    return rows
